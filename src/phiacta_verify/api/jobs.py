"""Submit/status/result endpoints for verification jobs."""

from __future__ import annotations

import hashlib
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from phiacta_verify.models.enums import JobStatus, RunnerType
from phiacta_verify.models.job import (
    ExpectedOutput,
    ResourceLimits,
    VerificationJob,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class SubmitJobRequest(BaseModel):
    """Request body for ``POST /v1/jobs``."""

    claim_id: UUID = Field(description="Identifier of the scientific claim.")
    runner_type: RunnerType = Field(description="Execution environment to use.")
    code_content: str = Field(description="Source code to execute in the sandbox.")
    environment_spec: dict | None = Field(
        default=None,
        description="Optional environment specification (pip requirements, etc.).",
    )
    expected_outputs: list[ExpectedOutput] | None = Field(
        default=None,
        description="Artifacts to compare against after execution.",
    )
    resource_limits: ResourceLimits | None = Field(
        default=None,
        description="Sandbox resource constraints. Defaults apply if omitted.",
    )
    submitted_by: str = Field(description="User or service that submitted the job.")


class SubmitJobResponse(BaseModel):
    """Response body for ``POST /v1/jobs``."""

    job_id: UUID
    status: JobStatus
    code_hash: str


class JobStatusResponse(BaseModel):
    """Response body for ``GET /v1/jobs/{job_id}``."""

    job_id: str
    status: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=SubmitJobResponse, status_code=201)
async def submit_job(body: SubmitJobRequest, request: Request) -> SubmitJobResponse:
    """Submit a new verification job.

    Validates code size against the configured maximum, computes a SHA-256
    hash of the code content, creates a :class:`VerificationJob`, enqueues
    it via the job queue, and returns the job ID, initial status, and code
    hash.
    """
    settings = request.app.state.settings
    queue = request.app.state.queue

    # Validate code size.
    code_bytes = body.code_content.encode("utf-8")
    if len(code_bytes) > settings.max_code_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Code content exceeds maximum allowed size "
                f"({len(code_bytes):,} bytes > {settings.max_code_size_bytes:,} bytes)."
            ),
        )

    code_hash = hashlib.sha256(code_bytes).hexdigest()

    job = VerificationJob(
        claim_id=body.claim_id,
        runner_type=body.runner_type,
        code_hash=code_hash,
        code_content=body.code_content,
        environment_spec=body.environment_spec,
        expected_outputs=body.expected_outputs,
        resource_limits=body.resource_limits or ResourceLimits(),
        submitted_by=body.submitted_by,
    )

    await queue.enqueue(job)

    logger.info(
        "Job submitted: id=%s runner=%s claim=%s",
        job.id,
        job.runner_type.value,
        job.claim_id,
    )

    return SubmitJobResponse(
        job_id=job.id,
        status=JobStatus.QUEUED,
        code_hash=code_hash,
    )


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: UUID, request: Request) -> JobStatusResponse:
    """Get the current status of a verification job."""
    queue = request.app.state.queue

    status = await queue.get_status(str(job_id))
    if status is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    return JobStatusResponse(
        job_id=str(job_id),
        status=status.value,
    )


@router.get("/{job_id}/result")
async def get_job_result(job_id: UUID, request: Request) -> dict:
    """Get the verification result for a completed job.

    Returns the full :class:`VerificationResult` as JSON, or 404 if no
    result has been stored yet.
    """
    queue = request.app.state.queue

    result = await queue.get_result(str(job_id))
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No result found for job {job_id}. The job may still be running.",
        )

    return result.model_dump(mode="json")


@router.get("", response_model=list[JobStatusResponse])
async def list_jobs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of jobs to return."),
) -> list[JobStatusResponse]:
    """List recent verification jobs ordered by creation time (newest first)."""
    queue = request.app.state.queue

    jobs = await queue.list_recent_jobs(limit=limit)
    return [
        JobStatusResponse(job_id=j["job_id"], status=j["status"])
        for j in jobs
    ]

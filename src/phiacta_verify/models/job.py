"""VerificationJob, ResourceLimits, and ExpectedOutput models."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from phiacta_verify.models.enums import ComparisonMethod, JobStatus, RunnerType


class ResourceLimits(BaseModel):
    """Hard resource limits enforced by the sandbox container."""

    cpu_seconds: int = Field(
        default=120,
        gt=0,
        description="Maximum CPU time in seconds.",
    )
    memory_mb: int = Field(
        default=2048,
        gt=0,
        description="Maximum resident memory in megabytes.",
    )
    disk_mb: int = Field(
        default=256,
        gt=0,
        description="Maximum writable disk space in megabytes.",
    )
    timeout_seconds: int = Field(
        default=120,
        gt=0,
        description="Wall-clock timeout for the entire execution.",
    )
    pids_limit: int = Field(
        default=64,
        gt=0,
        description="Maximum number of concurrent processes/threads.",
    )


class ExpectedOutput(BaseModel):
    """An expected artifact to compare against the runner's actual output."""

    name: str = Field(
        description="Logical name of the output artifact (e.g. 'result.csv', 'plot.png').",
    )
    content: bytes | None = Field(
        default=None,
        description="Raw bytes of the expected output. Mutually supplementary with content_hash.",
    )
    content_hash: str | None = Field(
        default=None,
        description="SHA-256 hex digest of the expected output.",
    )
    comparison_method: ComparisonMethod = Field(
        default=ComparisonMethod.EXACT,
        description="Algorithm used to compare actual vs. expected output.",
    )
    tolerance: float | None = Field(
        default=None,
        ge=0,
        description="Tolerance parameter for NUMERICAL_TOLERANCE or STATISTICAL comparisons.",
    )


class VerificationJob(BaseModel):
    """A single verification job submitted for sandboxed execution."""

    id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this verification job.",
    )
    claim_id: UUID = Field(
        description="Identifier of the scientific claim being verified.",
    )
    runner_type: RunnerType = Field(
        description="Execution environment to use for this job.",
    )
    code_hash: str = Field(
        description="SHA-256 hex digest of the code content for integrity checking.",
    )
    code_content: str = Field(
        description="The source code to execute inside the sandbox.",
    )
    environment_spec: dict | None = Field(  # type: ignore[type-arg]
        default=None,
        description=(
            "Optional environment specification (e.g. conda env, pip requirements, "
            "Julia Project.toml) serialised as a dictionary."
        ),
    )
    expected_outputs: list[ExpectedOutput] | None = Field(
        default=None,
        description="Artifacts to compare against after execution.",
    )
    resource_limits: ResourceLimits = Field(
        default_factory=ResourceLimits,
        description="Sandbox resource constraints for this job.",
    )
    status: JobStatus = Field(
        default=JobStatus.PENDING,
        description="Current lifecycle status of the job.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when the job was created.",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp of the most recent status change.",
    )
    submitted_by: str = Field(
        description="Identifier of the user or service that submitted this job.",
    )

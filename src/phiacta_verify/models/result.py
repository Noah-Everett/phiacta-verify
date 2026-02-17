"""VerificationResult and OutputComparison models."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from phiacta_verify.models.enums import ComparisonMethod, VerificationLevel


class OutputComparison(BaseModel):
    """Result of comparing a single actual output artifact against its expected value."""

    name: str = Field(
        description="Logical name of the compared output artifact.",
    )
    matched: bool = Field(
        description="Whether the comparison passed according to the chosen method.",
    )
    method: ComparisonMethod = Field(
        description="Comparison algorithm that was used.",
    )
    score: float = Field(
        description=(
            "Numeric similarity score. Semantics depend on method: "
            "1.0 = perfect match for EXACT/NUMERICAL_TOLERANCE, "
            "p-value for STATISTICAL, hash similarity for PERCEPTUAL_HASH."
        ),
    )
    details: dict | None = Field(  # type: ignore[type-arg]
        default=None,
        description="Optional method-specific metadata (e.g. diff snippet, test statistic).",
    )


class VerificationResult(BaseModel):
    """Immutable record produced after a verification job completes."""

    id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this result.",
    )
    job_id: UUID = Field(
        description="Identifier of the verification job that produced this result.",
    )
    claim_id: UUID = Field(
        description="Identifier of the scientific claim that was verified.",
    )
    verification_level: VerificationLevel = Field(
        description="Highest verification level achieved by this run.",
    )
    passed: bool = Field(
        description="Overall pass/fail verdict for the verification.",
    )
    code_hash: str = Field(
        description="SHA-256 hex digest of the code that was executed.",
    )
    signature: str = Field(
        default="",
        description="Ed25519 signature over the canonical result payload.",
    )
    execution_time_seconds: float = Field(
        ge=0,
        description="Wall-clock execution time of the sandboxed run in seconds.",
    )
    outputs_matched: list[OutputComparison] | None = Field(
        default=None,
        description="Per-artifact comparison results, if expected outputs were provided.",
    )
    stdout: str | None = Field(
        default=None,
        description="Captured standard output from the sandboxed execution.",
    )
    stderr: str | None = Field(
        default=None,
        description="Captured standard error from the sandboxed execution.",
    )
    error_message: str | None = Field(
        default=None,
        description="Human-readable error message if the job failed.",
    )
    runner_image: str = Field(
        description="Container image (name:tag) used for execution.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when this result was recorded.",
    )

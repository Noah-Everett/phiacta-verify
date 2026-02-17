"""VerificationLevel, RunnerType, JobStatus, and ComparisonMethod enums."""

from enum import StrEnum


class VerificationLevel(StrEnum):
    """Hierarchical verification levels for scientific claims.

    Each level subsumes all guarantees of levels below it:
      L0 - No verification has been performed.
      L1 - Code parses without syntax errors.
      L2 - Code executes to completion without runtime errors.
      L3 - Outputs match expected values via deterministic comparison.
      L4 - Outputs match expected distributions via statistical tests.
      L5 - Results independently replicated by a separate runner/environment.
      L6 - Correctness established through formal proof (e.g. Lean 4).
    """

    L0_UNVERIFIED = "L0_UNVERIFIED"
    L1_SYNTAX_VERIFIED = "L1_SYNTAX_VERIFIED"
    L2_EXECUTION_VERIFIED = "L2_EXECUTION_VERIFIED"
    L3_OUTPUT_VERIFIED_DETERMINISTIC = "L3_OUTPUT_VERIFIED_DETERMINISTIC"
    L4_OUTPUT_VERIFIED_STATISTICAL = "L4_OUTPUT_VERIFIED_STATISTICAL"
    L5_INDEPENDENTLY_REPLICATED = "L5_INDEPENDENTLY_REPLICATED"
    L6_FORMALLY_PROVEN = "L6_FORMALLY_PROVEN"


class RunnerType(StrEnum):
    """Supported execution environments for verification jobs."""

    PYTHON_SCRIPT = "PYTHON_SCRIPT"
    PYTHON_NOTEBOOK = "PYTHON_NOTEBOOK"
    R_SCRIPT = "R_SCRIPT"
    R_MARKDOWN = "R_MARKDOWN"
    JULIA = "JULIA"
    LEAN4 = "LEAN4"
    SYMPY = "SYMPY"
    SAGE = "SAGE"


class JobStatus(StrEnum):
    """Lifecycle states for a verification job."""

    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"


class ComparisonMethod(StrEnum):
    """Methods for comparing actual outputs against expected outputs."""

    EXACT = "EXACT"
    NUMERICAL_TOLERANCE = "NUMERICAL_TOLERANCE"
    STATISTICAL = "STATISTICAL"
    PERCEPTUAL_HASH = "PERCEPTUAL_HASH"

"""Abstract runner interface and shared data structures."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from phiacta_verify.models.enums import RunnerType, VerificationLevel
from phiacta_verify.models.job import VerificationJob


@dataclass
class PreparedExecution:
    """Everything the sandbox needs to execute a verification job.

    Attributes
    ----------
    image:
        Docker image name:tag to run.
    command:
        Command and arguments to execute inside the container.
    code_files:
        Mapping of ``relative_path -> source_code`` placed under ``/code/``.
    data_files:
        Optional mapping of ``relative_path -> raw_bytes`` placed under
        ``/data/``.
    env_vars:
        Optional environment variables to set inside the container.
    """

    image: str
    command: list[str]
    code_files: dict[str, str]  # filename -> content
    data_files: dict[str, bytes] | None = None
    env_vars: dict[str, str] = field(default_factory=dict)


@dataclass
class RunnerOutput:
    """Structured output produced by parsing sandbox results.

    Attributes
    ----------
    outputs:
        Mapping of ``filename -> raw_bytes`` for output artifacts.
    logs:
        Captured standard output from the execution.
    errors:
        Captured standard error from the execution.
    verification_level:
        The highest verification level achieved by this run.
    success:
        Whether the run is considered successful.
    """

    outputs: dict[str, bytes]  # filename -> content
    logs: str
    errors: str
    verification_level: VerificationLevel
    success: bool


class BaseRunner(ABC):
    """Abstract base class for all language-specific runners.

    Subclasses must set class-level attributes ``runner_type``,
    ``default_image``, and ``default_timeout``, and implement both
    :meth:`prepare` and :meth:`parse_output`.
    """

    runner_type: RunnerType
    default_image: str
    default_timeout: int

    @abstractmethod
    def prepare(self, job: VerificationJob) -> PreparedExecution:
        """Prepare execution environment from a VerificationJob.

        Translates the job's code content and metadata into concrete
        files, commands, and Docker image selection.

        Parameters
        ----------
        job:
            The verification job to prepare for execution.

        Returns
        -------
        PreparedExecution
            Fully specified execution plan for the sandbox.
        """
        ...

    @abstractmethod
    def parse_output(
        self,
        exit_code: int,
        stdout: str,
        stderr: str,
        output_files: dict[str, bytes],
    ) -> RunnerOutput:
        """Parse sandbox results into structured output.

        Parameters
        ----------
        exit_code:
            Process exit code from the container (0 = success).
        stdout:
            Captured standard output.
        stderr:
            Captured standard error.
        output_files:
            Files extracted from ``/output/`` in the container.

        Returns
        -------
        RunnerOutput
            Structured execution result with verification level.
        """
        ...

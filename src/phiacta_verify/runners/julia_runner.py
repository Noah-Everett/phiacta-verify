"""Julia runner."""

from __future__ import annotations

from phiacta_verify.models.enums import RunnerType, VerificationLevel
from phiacta_verify.models.job import VerificationJob
from phiacta_verify.runners.base import BaseRunner, PreparedExecution, RunnerOutput


class JuliaRunner(BaseRunner):
    """Runner for Julia scripts (``JULIA``).

    The code is placed at ``/code/script.jl`` and executed with
    ``julia /code/script.jl``.
    """

    runner_type: RunnerType = RunnerType.JULIA
    default_image: str = "phiacta-verify-runner-julia:latest"
    default_timeout: int = 120

    # ------------------------------------------------------------------
    # BaseRunner interface
    # ------------------------------------------------------------------

    def prepare(self, job: VerificationJob) -> PreparedExecution:
        """Prepare execution environment for a Julia job.

        Parameters
        ----------
        job:
            The verification job.  ``job.runner_type`` must be ``JULIA``.

        Returns
        -------
        PreparedExecution
        """
        code_files: dict[str, str] = {"script.jl": job.code_content}
        command: list[str] = ["julia", "/code/script.jl"]

        env_vars: dict[str, str] = {}
        if job.environment_spec and "env" in job.environment_spec:
            env_vars.update(job.environment_spec["env"])

        return PreparedExecution(
            image=self.default_image,
            command=command,
            code_files=code_files,
            data_files=None,
            env_vars=env_vars,
        )

    def parse_output(
        self,
        exit_code: int,
        stdout: str,
        stderr: str,
        output_files: dict[str, bytes],
    ) -> RunnerOutput:
        """Parse sandbox results for a Julia execution.

        An exit code of 0 yields ``L2_EXECUTION_VERIFIED``.  Any non-zero
        exit code is treated as a failure at ``L0_UNVERIFIED``.
        """
        if exit_code == 0:
            return RunnerOutput(
                outputs=output_files,
                logs=stdout,
                errors=stderr,
                verification_level=VerificationLevel.L2_EXECUTION_VERIFIED,
                success=True,
            )

        return RunnerOutput(
            outputs=output_files,
            logs=stdout,
            errors=stderr,
            verification_level=VerificationLevel.L0_UNVERIFIED,
            success=False,
        )

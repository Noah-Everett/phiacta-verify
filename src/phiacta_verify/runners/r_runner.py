"""R script and R Markdown runner."""

from __future__ import annotations

from phiacta_verify.models.enums import RunnerType, VerificationLevel
from phiacta_verify.models.job import VerificationJob
from phiacta_verify.runners.base import BaseRunner, PreparedExecution, RunnerOutput


class RRunner(BaseRunner):
    """Runner for R scripts (``R_SCRIPT``) and R Markdown documents (``R_MARKDOWN``).

    For plain R scripts the code is placed at ``/code/script.R`` and executed
    with ``Rscript /code/script.R``.

    For R Markdown files the code is placed at ``/code/input.Rmd`` and rendered
    via ``rmarkdown::render()`` with output directed to ``/output/``.
    """

    runner_type: RunnerType = RunnerType.R_SCRIPT
    default_image: str = "phiacta-verify-runner-r:latest"
    default_timeout: int = 120

    # ------------------------------------------------------------------
    # BaseRunner interface
    # ------------------------------------------------------------------

    def prepare(self, job: VerificationJob) -> PreparedExecution:
        """Prepare execution environment for an R job.

        Parameters
        ----------
        job:
            The verification job.  ``job.runner_type`` must be
            ``R_SCRIPT`` or ``R_MARKDOWN``.

        Returns
        -------
        PreparedExecution
        """
        code_files: dict[str, str] = {}
        command: list[str]

        if job.runner_type == RunnerType.R_MARKDOWN:
            code_files["input.Rmd"] = job.code_content
            command = [
                "Rscript",
                "-e",
                "rmarkdown::render('/code/input.Rmd', output_dir='/output/')",
            ]
        else:
            # Plain R script.
            code_files["script.R"] = job.code_content
            command = ["Rscript", "/code/script.R"]

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
        """Parse sandbox results for an R execution.

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

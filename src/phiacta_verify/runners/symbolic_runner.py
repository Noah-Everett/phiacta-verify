"""SymPy and SageMath symbolic computation runner."""

from __future__ import annotations

from phiacta_verify.models.enums import RunnerType, VerificationLevel
from phiacta_verify.models.job import VerificationJob
from phiacta_verify.runners.base import BaseRunner, PreparedExecution, RunnerOutput


class SymbolicRunner(BaseRunner):
    """Runner for symbolic computation via SymPy (``SYMPY``) or SageMath (``SAGE``).

    Both SymPy and Sage run inside the Python runner image since SymPy
    is a pure-Python library and SageMath is typically invoked through
    its Python interface.  The code is placed at ``/code/symbolic.py``
    and executed with ``python /code/symbolic.py``.

    A successful run (exit code 0) achieves ``L2_EXECUTION_VERIFIED``.
    L3 requires comparing outputs against expected values, which is
    handled by the worker's comparator step, not the runner itself.
    """

    runner_type: RunnerType = RunnerType.SYMPY
    default_image: str = "phiacta-verify-runner-python:latest"
    default_timeout: int = 60

    # ------------------------------------------------------------------
    # BaseRunner interface
    # ------------------------------------------------------------------

    def prepare(self, job: VerificationJob) -> PreparedExecution:
        """Prepare execution environment for a symbolic computation job.

        Parameters
        ----------
        job:
            The verification job.  ``job.runner_type`` must be ``SYMPY``
            or ``SAGE``.

        Returns
        -------
        PreparedExecution
        """
        code_files: dict[str, str] = {"symbolic.py": job.code_content}
        command: list[str] = ["python", "/code/symbolic.py"]

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
        """Parse sandbox results for a symbolic computation.

        An exit code of 0 yields ``L2_EXECUTION_VERIFIED``.
        Any non-zero exit code indicates failure at ``L0_UNVERIFIED``.
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

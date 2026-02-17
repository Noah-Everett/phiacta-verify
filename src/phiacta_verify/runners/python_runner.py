"""Python script and notebook runner."""

from __future__ import annotations

import textwrap

from phiacta_verify.models.enums import RunnerType, VerificationLevel
from phiacta_verify.models.job import VerificationJob
from phiacta_verify.runners.base import BaseRunner, PreparedExecution, RunnerOutput


class PythonRunner(BaseRunner):
    """Runner for Python scripts (``PYTHON_SCRIPT``) and Jupyter notebooks (``PYTHON_NOTEBOOK``).

    For plain Python scripts the code is written directly to ``/code/run.py``
    and executed with ``python /code/run.py``.

    For notebooks the ``.ipynb`` file is placed under ``/code/`` alongside a
    thin wrapper script that converts it to a plain ``.py`` file via
    ``jupyter nbconvert`` and then executes the result.  This avoids the need
    for a running Jupyter kernel inside the sandbox.
    """

    runner_type: RunnerType = RunnerType.PYTHON_SCRIPT
    default_image: str = "phiacta-verify-runner-python:latest"
    default_timeout: int = 120

    # ------------------------------------------------------------------
    # Notebook wrapper template
    # ------------------------------------------------------------------

    _NOTEBOOK_WRAPPER: str = textwrap.dedent("""\
        \"\"\"Wrapper that converts an .ipynb notebook to .py and executes it.\"\"\"
        import subprocess
        import sys

        # Convert notebook to plain Python script.
        convert_result = subprocess.run(
            [
                sys.executable, "-m", "jupyter", "nbconvert",
                "--to", "script",
                "--output-dir", "/code",
                "/code/notebook.ipynb",
            ],
            capture_output=True,
            text=True,
        )

        if convert_result.returncode != 0:
            print(convert_result.stderr, file=sys.stderr)
            sys.exit(convert_result.returncode)

        # Execute the converted script.
        exec_result = subprocess.run(
            [sys.executable, "/code/notebook.py"],
            capture_output=False,
        )
        sys.exit(exec_result.returncode)
    """)

    # ------------------------------------------------------------------
    # BaseRunner interface
    # ------------------------------------------------------------------

    def prepare(self, job: VerificationJob) -> PreparedExecution:
        """Prepare execution environment for a Python job.

        Parameters
        ----------
        job:
            The verification job.  ``job.runner_type`` must be
            ``PYTHON_SCRIPT`` or ``PYTHON_NOTEBOOK``.

        Returns
        -------
        PreparedExecution
        """
        code_files: dict[str, str] = {}
        command: list[str]

        if job.runner_type == RunnerType.PYTHON_NOTEBOOK:
            # Place the raw notebook and a wrapper that converts + runs it.
            code_files["notebook.ipynb"] = job.code_content
            code_files["run.py"] = self._NOTEBOOK_WRAPPER
            command = ["python", "/code/run.py"]
        else:
            # Plain Python script.
            code_files["run.py"] = job.code_content
            command = ["python", "/code/run.py"]

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
        """Parse sandbox results for a Python execution.

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

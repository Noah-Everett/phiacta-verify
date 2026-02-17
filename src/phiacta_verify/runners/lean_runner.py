"""Lean 4 proof checker runner."""

from __future__ import annotations

from phiacta_verify.models.enums import RunnerType, VerificationLevel
from phiacta_verify.models.job import VerificationJob
from phiacta_verify.runners.base import BaseRunner, PreparedExecution, RunnerOutput


class LeanRunner(BaseRunner):
    """Runner for Lean 4 formal proofs (``LEAN4``).

    The proof file is placed at ``/code/proof.lean`` and checked with
    ``lean /code/proof.lean``.

    A successful check (exit code 0) is the strongest verification level
    in the hierarchy: ``L6_FORMALLY_PROVEN``.  Lean guarantees that the
    proof term type-checks, which implies mathematical correctness of the
    stated theorem.
    """

    runner_type: RunnerType = RunnerType.LEAN4
    default_image: str = "phiacta-verify-runner-lean4:latest"
    default_timeout: int = 300  # Lean proofs can be slow to elaborate

    # ------------------------------------------------------------------
    # BaseRunner interface
    # ------------------------------------------------------------------

    def prepare(self, job: VerificationJob) -> PreparedExecution:
        """Prepare execution environment for a Lean 4 job.

        Parameters
        ----------
        job:
            The verification job.  ``job.runner_type`` must be ``LEAN4``.

        Returns
        -------
        PreparedExecution
        """
        code_files: dict[str, str] = {"proof.lean": job.code_content}
        command: list[str] = ["lean", "/code/proof.lean"]

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
        """Parse sandbox results for a Lean 4 proof check.

        An exit code of 0 means the proof was fully elaborated and
        type-checked by the Lean kernel, yielding ``L6_FORMALLY_PROVEN``.
        Any non-zero exit code indicates a proof failure at ``L0_UNVERIFIED``.
        """
        if exit_code == 0:
            return RunnerOutput(
                outputs=output_files,
                logs=stdout,
                errors=stderr,
                verification_level=VerificationLevel.L6_FORMALLY_PROVEN,
                success=True,
            )

        return RunnerOutput(
            outputs=output_files,
            logs=stdout,
            errors=stderr,
            verification_level=VerificationLevel.L0_UNVERIFIED,
            success=False,
        )

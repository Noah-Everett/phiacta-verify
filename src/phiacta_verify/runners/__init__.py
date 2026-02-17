"""Execution runners for all supported verification languages.

Each runner translates a :class:`~phiacta_verify.models.job.VerificationJob`
into a :class:`PreparedExecution` that the sandbox can run, and parses
container output back into a :class:`RunnerOutput`.

Use :func:`get_runner` to obtain the correct runner instance for a given
:class:`~phiacta_verify.models.enums.RunnerType`.
"""

from __future__ import annotations

from phiacta_verify.models.enums import RunnerType
from phiacta_verify.runners.base import BaseRunner, PreparedExecution, RunnerOutput
from phiacta_verify.runners.julia_runner import JuliaRunner
from phiacta_verify.runners.lean_runner import LeanRunner
from phiacta_verify.runners.python_runner import PythonRunner
from phiacta_verify.runners.r_runner import RRunner
from phiacta_verify.runners.symbolic_runner import SymbolicRunner

__all__ = [
    "BaseRunner",
    "JuliaRunner",
    "LeanRunner",
    "PreparedExecution",
    "PythonRunner",
    "RRunner",
    "RunnerOutput",
    "SymbolicRunner",
    "get_runner",
]

# ---------------------------------------------------------------------------
# Runner type -> runner class mapping
# ---------------------------------------------------------------------------

_RUNNER_MAP: dict[RunnerType, type[BaseRunner]] = {
    RunnerType.PYTHON_SCRIPT: PythonRunner,
    RunnerType.PYTHON_NOTEBOOK: PythonRunner,
    RunnerType.R_SCRIPT: RRunner,
    RunnerType.R_MARKDOWN: RRunner,
    RunnerType.JULIA: JuliaRunner,
    RunnerType.LEAN4: LeanRunner,
    RunnerType.SYMPY: SymbolicRunner,
    RunnerType.SAGE: SymbolicRunner,
}


def get_runner(runner_type: RunnerType) -> BaseRunner:
    """Return a runner instance appropriate for the given *runner_type*.

    Parameters
    ----------
    runner_type:
        The :class:`~phiacta_verify.models.enums.RunnerType` identifying
        the execution environment.

    Returns
    -------
    BaseRunner
        An instance of the concrete runner subclass.

    Raises
    ------
    ValueError
        If *runner_type* is not supported.
    """
    runner_cls = _RUNNER_MAP.get(runner_type)
    if runner_cls is None:
        raise ValueError(
            f"Unsupported runner type: {runner_type!r}. "
            f"Supported types: {sorted(_RUNNER_MAP.keys())}"
        )
    return runner_cls()

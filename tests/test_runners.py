"""Tests for verification runners."""

from __future__ import annotations

from uuid import uuid4

import pytest

from phiacta_verify.models.enums import RunnerType, VerificationLevel
from phiacta_verify.models.job import VerificationJob
from phiacta_verify.runners import get_runner
from phiacta_verify.runners.python_runner import PythonRunner
from phiacta_verify.runners.r_runner import RRunner
from phiacta_verify.runners.julia_runner import JuliaRunner
from phiacta_verify.runners.lean_runner import LeanRunner
from phiacta_verify.runners.symbolic_runner import SymbolicRunner


def _make_job(runner_type: RunnerType, code: str = "print('hi')", **kwargs) -> VerificationJob:
    return VerificationJob(
        claim_id=uuid4(),
        runner_type=runner_type,
        code_hash="abc123",
        code_content=code,
        submitted_by="test",
        **kwargs,
    )


# ======================================================================
# get_runner factory
# ======================================================================


class TestGetRunner:
    @pytest.mark.parametrize(
        "runner_type, expected_cls",
        [
            (RunnerType.PYTHON_SCRIPT, PythonRunner),
            (RunnerType.PYTHON_NOTEBOOK, PythonRunner),
            (RunnerType.R_SCRIPT, RRunner),
            (RunnerType.R_MARKDOWN, RRunner),
            (RunnerType.JULIA, JuliaRunner),
            (RunnerType.LEAN4, LeanRunner),
            (RunnerType.SYMPY, SymbolicRunner),
            (RunnerType.SAGE, SymbolicRunner),
        ],
    )
    def test_returns_correct_class(self, runner_type, expected_cls):
        runner = get_runner(runner_type)
        assert isinstance(runner, expected_cls)

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unsupported runner type"):
            get_runner("NONEXISTENT")  # type: ignore[arg-type]


# ======================================================================
# PythonRunner
# ======================================================================


class TestPythonRunner:
    def setup_method(self):
        self.runner = PythonRunner()

    def test_prepare_script(self):
        job = _make_job(RunnerType.PYTHON_SCRIPT, code="print(1)")
        prep = self.runner.prepare(job)
        assert prep.image == "phiacta-verify-runner-python:latest"
        assert prep.command == ["python", "/code/run.py"]
        assert "run.py" in prep.code_files
        assert prep.code_files["run.py"] == "print(1)"

    def test_prepare_notebook(self):
        job = _make_job(RunnerType.PYTHON_NOTEBOOK, code='{"cells":[]}')
        prep = self.runner.prepare(job)
        assert "notebook.ipynb" in prep.code_files
        assert "run.py" in prep.code_files
        assert prep.command == ["python", "/code/run.py"]

    def test_prepare_env_vars(self):
        job = _make_job(
            RunnerType.PYTHON_SCRIPT,
            environment_spec={"env": {"MY_VAR": "value"}},
        )
        prep = self.runner.prepare(job)
        assert prep.env_vars == {"MY_VAR": "value"}

    def test_parse_output_success(self):
        out = self.runner.parse_output(0, "output", "", {})
        assert out.success is True
        assert out.verification_level == VerificationLevel.L2_EXECUTION_VERIFIED

    def test_parse_output_failure(self):
        out = self.runner.parse_output(1, "", "error", {})
        assert out.success is False
        assert out.verification_level == VerificationLevel.L0_UNVERIFIED


# ======================================================================
# LeanRunner
# ======================================================================


class TestLeanRunner:
    def setup_method(self):
        self.runner = LeanRunner()

    def test_prepare(self):
        job = _make_job(RunnerType.LEAN4, code="theorem foo : True := trivial")
        prep = self.runner.prepare(job)
        assert prep.image == "phiacta-verify-runner-lean4:latest"
        assert prep.command == ["lean", "/code/proof.lean"]
        assert prep.code_files["proof.lean"] == job.code_content

    def test_parse_output_success_is_L6(self):
        out = self.runner.parse_output(0, "", "", {})
        assert out.success is True
        assert out.verification_level == VerificationLevel.L6_FORMALLY_PROVEN

    def test_parse_output_failure(self):
        out = self.runner.parse_output(1, "", "type mismatch", {})
        assert out.success is False
        assert out.verification_level == VerificationLevel.L0_UNVERIFIED


# ======================================================================
# SymbolicRunner
# ======================================================================


class TestSymbolicRunner:
    def setup_method(self):
        self.runner = SymbolicRunner()

    def test_prepare_sympy(self):
        job = _make_job(RunnerType.SYMPY)
        prep = self.runner.prepare(job)
        assert prep.command == ["python", "/code/symbolic.py"]

    def test_success_is_L2_not_L3(self):
        """SymbolicRunner should claim L2, not L3 -- L3 requires output comparison."""
        out = self.runner.parse_output(0, "result", "", {})
        assert out.success is True
        assert out.verification_level == VerificationLevel.L2_EXECUTION_VERIFIED


# ======================================================================
# RRunner
# ======================================================================


class TestRRunner:
    def setup_method(self):
        self.runner = RRunner()

    def test_prepare_script(self):
        job = _make_job(RunnerType.R_SCRIPT, code="cat('hello')")
        prep = self.runner.prepare(job)
        assert prep.command == ["Rscript", "/code/script.R"]

    def test_prepare_rmarkdown(self):
        job = _make_job(RunnerType.R_MARKDOWN, code="---\ntitle: test\n---\n")
        prep = self.runner.prepare(job)
        assert "input.Rmd" in prep.code_files
        assert "rmarkdown::render" in prep.command[2]

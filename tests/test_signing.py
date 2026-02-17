"""Tests for Ed25519 signing."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from phiacta_verify.models.enums import VerificationLevel
from phiacta_verify.models.result import VerificationResult
from phiacta_verify.signing.ed25519 import ResultSigner


def _make_result(**kwargs) -> VerificationResult:
    defaults = {
        "job_id": uuid4(),
        "claim_id": uuid4(),
        "verification_level": VerificationLevel.L2_EXECUTION_VERIFIED,
        "passed": True,
        "code_hash": "abcdef1234567890" * 4,
        "execution_time_seconds": 1.5,
        "runner_image": "phiacta-verify-runner-python:latest",
    }
    defaults.update(kwargs)
    return VerificationResult(**defaults)


class TestResultSigner:
    """Tests for ResultSigner."""

    def test_sign_produces_nonempty_string(self):
        signer = ResultSigner()
        result = _make_result()
        sig = signer.sign(result)
        assert isinstance(sig, str)
        assert len(sig) > 0

    def test_verify_valid_signature(self):
        signer = ResultSigner()
        result = _make_result()
        sig = signer.sign(result)
        assert signer.verify(result, sig) is True

    def test_verify_tampered_result(self):
        signer = ResultSigner()
        result = _make_result()
        sig = signer.sign(result)
        # Tamper with the result.
        result.passed = False
        assert signer.verify(result, sig) is False

    def test_verify_wrong_signature(self):
        signer = ResultSigner()
        result = _make_result()
        assert signer.verify(result, "badsignature") is False

    def test_canonical_payload_deterministic(self):
        signer = ResultSigner()
        result = _make_result()
        p1 = signer.canonical_payload(result)
        p2 = signer.canonical_payload(result)
        assert p1 == p2

    def test_canonical_payload_is_json(self):
        import json
        signer = ResultSigner()
        result = _make_result()
        payload = signer.canonical_payload(result)
        parsed = json.loads(payload)
        assert "job_id" in parsed
        assert "code_hash" in parsed
        assert "passed" in parsed

    def test_get_public_key_pem(self):
        signer = ResultSigner()
        pem = signer.get_public_key_pem()
        assert "BEGIN PUBLIC KEY" in pem

    def test_save_and_load_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = str(Path(tmpdir) / "test_key.pem")
            signer1 = ResultSigner()
            signer1.save_private_key(key_path)

            # Load the key back.
            signer2 = ResultSigner(private_key_path=key_path)

            # Both should produce the same signature.
            result = _make_result()
            sig1 = signer1.sign(result)
            sig2 = signer2.sign(result)
            assert sig1 == sig2

    def test_ephemeral_key_warning(self, caplog):
        """When no key path is given, a warning should be logged."""
        import logging
        with caplog.at_level(logging.WARNING):
            ResultSigner()
        assert "ephemeral" in caplog.text.lower() or "dev mode" in caplog.text.lower()

    def test_different_signers_different_signatures(self):
        signer1 = ResultSigner()
        signer2 = ResultSigner()
        result = _make_result()
        sig1 = signer1.sign(result)
        sig2 = signer2.sign(result)
        # Ephemeral keys are different, so signatures should differ.
        assert sig1 != sig2

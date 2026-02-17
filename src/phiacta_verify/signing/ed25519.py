"""Ed25519 result signing and verification."""

import json
import base64
import logging
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization

logger = logging.getLogger(__name__)


class ResultSigner:
    """Signs and verifies VerificationResult objects using Ed25519.

    When instantiated with a path to an existing PEM-encoded private key,
    that key is loaded and used for all signing operations.  If no key is
    found an ephemeral key-pair is generated (suitable for development /
    testing only).
    """

    def __init__(self, private_key_path: str | None = None):
        if private_key_path and Path(private_key_path).exists():
            pem = Path(private_key_path).read_bytes()
            self._private_key: Ed25519PrivateKey = serialization.load_pem_private_key(
                pem, password=None
            )  # type: ignore[assignment]
        else:
            logger.warning(
                "No signing key found, generating ephemeral key (dev mode only)"
            )
            self._private_key = Ed25519PrivateKey.generate()
        self._public_key: Ed25519PublicKey = self._private_key.public_key()

    # ------------------------------------------------------------------
    # Canonical payload
    # ------------------------------------------------------------------

    def canonical_payload(self, result) -> bytes:
        """Deterministic JSON of critical fields for signing."""
        data = {
            "job_id": str(result.job_id),
            "claim_id": str(result.claim_id),
            "code_hash": result.code_hash,
            "verification_level": result.verification_level.value,
            "passed": result.passed,
            "execution_time_seconds": result.execution_time_seconds,
            "created_at": result.created_at.isoformat(),
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()

    # ------------------------------------------------------------------
    # Sign / verify
    # ------------------------------------------------------------------

    def sign(self, result) -> str:
        """Sign a VerificationResult, returning base64-encoded signature."""
        payload = self.canonical_payload(result)
        signature = self._private_key.sign(payload)
        return base64.b64encode(signature).decode()

    def verify(self, result, signature: str) -> bool:
        """Verify signature against a VerificationResult."""
        payload = self.canonical_payload(result)
        sig_bytes = base64.b64decode(signature)
        try:
            self._public_key.verify(sig_bytes, payload)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Key management helpers
    # ------------------------------------------------------------------

    def get_public_key_pem(self) -> str:
        """Return the public key in PEM format."""
        return self._public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    def save_private_key(self, path: str) -> None:
        """Persist the private key to *path* in PKCS8 PEM format."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        pem = self._private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        Path(path).write_bytes(pem)

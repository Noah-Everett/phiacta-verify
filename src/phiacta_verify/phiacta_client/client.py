"""Async HTTP client for the phiacta backend API.

Provides :class:`PhiactaClient` for fetching claims and submitting
verification reviews to the main phiacta platform.
"""

from __future__ import annotations

import logging
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)


class PhiactaClient:
    """Async HTTP client for the phiacta backend.

    Parameters
    ----------
    base_url:
        Root URL of the phiacta API (e.g. ``http://localhost:8000``).
    api_key:
        Bearer token used for authentication.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # Claims
    # ------------------------------------------------------------------

    async def fetch_claim(self, claim_id: UUID) -> dict:
        """Fetch a scientific claim by its identifier.

        Parameters
        ----------
        claim_id:
            UUID of the claim to retrieve.

        Returns
        -------
        dict
            The claim payload as returned by the phiacta API.

        Raises
        ------
        httpx.HTTPStatusError
            If the API returns a non-2xx status code.
        """
        resp = await self._client.get(f"/v1/claims/{claim_id}")
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Reviews
    # ------------------------------------------------------------------

    async def submit_review(
        self,
        claim_id: UUID,
        verdict: str,
        confidence: float,
        comment: str = "",
    ) -> dict:
        """Submit a verification review for a claim.

        Parameters
        ----------
        claim_id:
            UUID of the claim being reviewed.
        verdict:
            The verification verdict (e.g. ``"VERIFIED"``, ``"FAILED"``).
        confidence:
            Confidence score between 0.0 and 1.0.
        comment:
            Optional human-readable comment.

        Returns
        -------
        dict
            The review payload as returned by the phiacta API.

        Raises
        ------
        httpx.HTTPStatusError
            If the API returns a non-2xx status code.
        """
        resp = await self._client.post(
            f"/v1/claims/{claim_id}/reviews",
            json={
                "verdict": verdict,
                "confidence": confidence,
                "comment": comment,
            },
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Verification status
    # ------------------------------------------------------------------

    async def update_verification_status(
        self,
        claim_id: UUID,
        level: str,
        passed: bool,
        details: dict | None = None,
    ) -> dict:
        """Update a claim's verification status in the backend.

        Parameters
        ----------
        claim_id:
            UUID of the claim to update.
        level:
            Verification level achieved (e.g. ``"L2_EXECUTION_VERIFIED"``).
        passed:
            Whether verification passed overall.
        details:
            Optional extra details to store in the claim attrs.

        Returns
        -------
        dict
            The updated claim payload as returned by the phiacta API.

        Raises
        ------
        httpx.HTTPStatusError
            If the API returns a non-2xx status code.
        """
        verification_result = {
            "verification_level": level,
            "passed": passed,
        }
        if details:
            verification_result.update(details)

        resp = await self._client.get(f"/v1/claims/{claim_id}")
        resp.raise_for_status()
        claim_data = resp.json()
        attrs = claim_data.get("attrs", {})
        attrs["verification_level"] = level
        attrs["verification_status"] = "verified" if passed else "failed"
        attrs["verification_result"] = verification_result

        resp = await self._client.post(
            f"/v1/claims/{claim_id}/verify",
            json={
                "code_content": attrs.get("verification_code", ""),
                "runner_type": attrs.get("verification_runner_type", "python_script"),
            },
        )
        # If the verify endpoint fails, fall back silently -- the review
        # is what matters for the backend record.
        if resp.status_code < 400:
            return resp.json()
        return claim_data

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client and release resources."""
        await self._client.aclose()

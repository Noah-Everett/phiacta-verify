"""Perceptual hash / byte-similarity comparison for image outputs.

This module deliberately avoids any dependency on PIL, OpenCV, or other
image-processing libraries so that it can run inside the lightweight
verification service without extra native packages.

Strategy:

1. Compute SHA-256 hashes of both payloads.  If they match, the files are
   identical -- return score 1.0 immediately.
2. Otherwise, perform a byte-level comparison: walk both payloads and count
   the number of positions where the bytes agree.  The similarity ratio
   ``bytes_matching / bytes_total`` is the score, and the comparison passes
   when that ratio meets or exceeds the configured threshold.

This gives a rough but dependency-free measure of how much two binary
payloads differ.  It is most useful for detecting bit-exact matches and
flagging gross corruption; for true perceptual similarity (rotation, crop,
colour-space changes) a full image library would be needed.
"""

from __future__ import annotations

import hashlib

from phiacta_verify.comparators.base import BaseComparator, ComparisonResult
from phiacta_verify.models.enums import ComparisonMethod

_DEFAULT_THRESHOLD: float = 0.95


class ImageComparator(BaseComparator):
    """Compare binary payloads (typically images) by byte similarity.

    Keyword arguments accepted by :meth:`compare`:
        threshold (float): Minimum byte-similarity ratio to consider
            the outputs matched.  Default ``0.95`` (95 %).
    """

    def compare(self, expected: bytes, actual: bytes, **kwargs) -> ComparisonResult:
        threshold: float = kwargs.get("threshold", _DEFAULT_THRESHOLD)

        hash_expected = hashlib.sha256(expected).hexdigest()
        hash_actual = hashlib.sha256(actual).hexdigest()

        details: dict = {
            "hash_expected": hash_expected,
            "hash_actual": hash_actual,
            "size_expected": len(expected),
            "size_actual": len(actual),
        }

        # Fast path: identical files.
        if hash_expected == hash_actual:
            details["bytes_total"] = len(expected)
            details["bytes_matching"] = len(expected)
            details["similarity"] = 1.0
            return ComparisonResult(
                matched=True,
                method=ComparisonMethod.PERCEPTUAL_HASH,
                score=1.0,
                details=details,
            )

        # Byte-level comparison.
        bytes_total, bytes_matching = _byte_similarity(expected, actual)
        similarity = bytes_matching / bytes_total if bytes_total > 0 else 0.0

        details["bytes_total"] = bytes_total
        details["bytes_matching"] = bytes_matching
        details["similarity"] = similarity

        matched = similarity >= threshold

        return ComparisonResult(
            matched=matched,
            method=ComparisonMethod.PERCEPTUAL_HASH,
            score=similarity,
            details=details,
        )


def _byte_similarity(a: bytes, b: bytes) -> tuple[int, int]:
    """Count matching bytes between *a* and *b*.

    Bytes beyond the shorter payload are counted as mismatches.

    Returns:
        A ``(bytes_total, bytes_matching)`` tuple.
    """
    len_a = len(a)
    len_b = len(b)
    bytes_total = max(len_a, len_b)

    if bytes_total == 0:
        return 0, 0

    min_len = min(len_a, len_b)
    matching = 0

    # Compare the overlapping region.  Process in chunks to avoid creating
    # a huge intermediate list.
    chunk_size = 65536
    for offset in range(0, min_len, chunk_size):
        end = min(offset + chunk_size, min_len)
        matching += sum(
            a_byte == b_byte
            for a_byte, b_byte in zip(a[offset:end], b[offset:end])
        )

    return bytes_total, matching

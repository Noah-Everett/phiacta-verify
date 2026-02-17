"""Bit-for-bit (and text-aware) exact comparison."""

from __future__ import annotations

from phiacta_verify.comparators.base import BaseComparator, ComparisonResult
from phiacta_verify.models.enums import ComparisonMethod


class ExactComparator(BaseComparator):
    """Compares expected and actual outputs for exact equality.

    Two comparison strategies are attempted in order:

    1. **Text mode** -- if both inputs are valid UTF-8, decode them, strip
       trailing whitespace from every line and trailing newlines from the
       whole string, then compare.  This avoids false negatives caused by
       editors or runners appending/trimming whitespace.
    2. **Binary mode** -- fall back to raw byte-for-byte comparison.

    Keyword arguments accepted by :meth:`compare`:
        (none)
    """

    def compare(self, expected: bytes, actual: bytes, **kwargs) -> ComparisonResult:
        byte_len_expected = len(expected)
        byte_len_actual = len(actual)
        details: dict = {
            "byte_length_expected": byte_len_expected,
            "byte_length_actual": byte_len_actual,
        }

        # Attempt text-mode comparison first.
        try:
            text_expected = expected.decode("utf-8")
            text_actual = actual.decode("utf-8")

            normalized_expected = _normalize_text(text_expected)
            normalized_actual = _normalize_text(text_actual)

            matched = normalized_expected == normalized_actual
            details["mode"] = "text"
        except UnicodeDecodeError:
            # Not valid UTF-8 -- fall back to raw binary comparison.
            matched = expected == actual
            details["mode"] = "binary"

        return ComparisonResult(
            matched=matched,
            method=ComparisonMethod.EXACT,
            score=1.0 if matched else 0.0,
            details=details,
        )


def _normalize_text(text: str) -> str:
    """Strip trailing whitespace from each line and trailing newlines."""
    lines = text.splitlines()
    stripped = [line.rstrip() for line in lines]
    # Remove trailing empty lines, then rejoin.
    while stripped and stripped[-1] == "":
        stripped.pop()
    return "\n".join(stripped)

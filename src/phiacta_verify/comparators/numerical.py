"""Tolerance-based numerical comparison."""

from __future__ import annotations

import json
import math
import re
from typing import Sequence

from phiacta_verify.comparators.base import BaseComparator, ComparisonResult
from phiacta_verify.models.enums import ComparisonMethod

# Default tolerances -- identical semantics to numpy.allclose.
_DEFAULT_RTOL: float = 1e-10
_DEFAULT_ATOL: float = 1e-12

# Regex that matches a floating-point or integer literal, including optional
# sign, scientific notation, and the special tokens inf/-inf/nan.
_NUMBER_RE = re.compile(
    r"[+-]?"
    r"(?:"
    r"inf(?:inity)?"
    r"|nan"
    r"|(?:\d+\.?\d*|\.\d+)(?:[eEdD][+-]?\d+)?"
    r")",
    re.IGNORECASE,
)


class NumericalComparator(BaseComparator):
    """Compares sequences of numbers parsed from textual output.

    Numbers are extracted from the byte payloads using a liberal parser that
    understands:

    * One number per line
    * Comma-separated values (CSV rows)
    * JSON arrays (flat or nested -- all numeric leaves are collected)
    * Scientific notation (``1.23e-4``, ``1.23D+02``)
    * Special IEEE 754 tokens: ``nan``, ``inf``, ``-inf``

    Comparison semantics mirror ``numpy.allclose``:
        ``|expected - actual| <= atol + rtol * |expected|``

    with the addition that NaN is considered equal to NaN.

    Keyword arguments accepted by :meth:`compare`:
        rtol (float): Relative tolerance.  Default ``1e-10``.
        atol (float): Absolute tolerance.  Default ``1e-12``.
    """

    def compare(self, expected: bytes, actual: bytes, **kwargs) -> ComparisonResult:
        rtol: float = kwargs.get("rtol", _DEFAULT_RTOL)
        atol: float = kwargs.get("atol", _DEFAULT_ATOL)

        expected_values = _parse_numbers(expected)
        actual_values = _parse_numbers(actual)

        # If the two sequences have different lengths, report a mismatch but
        # still compare as many pairs as possible to give useful diagnostics.
        count = max(len(expected_values), len(actual_values))
        if count == 0:
            # Nothing to compare -- degenerate but technically a match.
            return ComparisonResult(
                matched=True,
                method=ComparisonMethod.NUMERICAL_TOLERANCE,
                score=1.0,
                details={
                    "max_relative_error": 0.0,
                    "max_absolute_error": 0.0,
                    "values_compared": 0,
                    "mismatches": [],
                },
            )

        mismatches: list[dict] = []
        max_rel_err: float = 0.0
        max_abs_err: float = 0.0

        # Length mismatch itself is a kind of error.
        length_mismatch = len(expected_values) != len(actual_values)
        pairs = min(len(expected_values), len(actual_values))

        for i in range(pairs):
            exp_val = expected_values[i]
            act_val = actual_values[i]
            abs_err, rel_err, ok = _values_close(exp_val, act_val, rtol, atol)
            max_abs_err = max(max_abs_err, abs_err)
            max_rel_err = max(max_rel_err, rel_err)
            if not ok:
                mismatches.append({
                    "index": i,
                    "expected": _format_value(exp_val),
                    "actual": _format_value(act_val),
                    "absolute_error": abs_err,
                    "relative_error": rel_err,
                })

        # Count unpaired values as mismatches.
        if length_mismatch:
            longer = expected_values if len(expected_values) > len(actual_values) else actual_values
            source = "expected" if len(expected_values) > len(actual_values) else "actual"
            for i in range(pairs, len(longer)):
                mismatches.append({
                    "index": i,
                    "expected": (
                        _format_value(expected_values[i])
                        if i < len(expected_values)
                        else "<missing>"
                    ),
                    "actual": (
                        _format_value(actual_values[i])
                        if i < len(actual_values)
                        else "<missing>"
                    ),
                    "absolute_error": float("inf"),
                    "relative_error": float("inf"),
                    "note": f"value only present in {source}",
                })
            # Treat length mismatch as infinite error.
            max_abs_err = float("inf")
            max_rel_err = float("inf")

        matched = len(mismatches) == 0
        # Score: 1 - max_relative_error, clamped to [0, 1].
        if math.isinf(max_rel_err) or math.isnan(max_rel_err):
            score = 0.0
        else:
            score = max(0.0, min(1.0, 1.0 - max_rel_err))

        return ComparisonResult(
            matched=matched,
            method=ComparisonMethod.NUMERICAL_TOLERANCE,
            score=score,
            details={
                "max_relative_error": max_rel_err,
                "max_absolute_error": max_abs_err,
                "values_compared": count,
                "mismatches": mismatches,
            },
        )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_numbers(data: bytes) -> list[float]:
    """Extract an ordered list of numbers from *data*.

    Tries JSON first (handles arrays, nested arrays, and objects with numeric
    values).  Falls back to regex extraction from the decoded text.
    """
    text = data.decode("utf-8", errors="replace")

    # Try JSON first.
    try:
        obj = json.loads(text)
        values: list[float] = []
        _collect_json_numbers(obj, values)
        if values:
            return values
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: regex scan.
    return [_to_float(m.group()) for m in _NUMBER_RE.finditer(text)]


def _collect_json_numbers(obj: object, acc: list[float]) -> None:
    """Recursively collect numeric leaves from a JSON structure."""
    if isinstance(obj, (int, float)):
        acc.append(float(obj))
    elif isinstance(obj, list):
        for item in obj:
            _collect_json_numbers(item, acc)
    elif isinstance(obj, dict):
        for value in obj.values():
            _collect_json_numbers(value, acc)


def _to_float(token: str) -> float:
    """Convert a string token to a float, handling Fortran-style ``D`` exponents."""
    # Replace Fortran-style exponent marker.
    normalized = re.sub(r"[dD]", "e", token)
    return float(normalized)


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------


def _values_close(
    expected: float,
    actual: float,
    rtol: float,
    atol: float,
) -> tuple[float, float, bool]:
    """Check whether two values are close within tolerance.

    Returns ``(absolute_error, relative_error, is_close)``.
    """
    # NaN == NaN for verification purposes.
    if math.isnan(expected) and math.isnan(actual):
        return 0.0, 0.0, True
    if math.isnan(expected) or math.isnan(actual):
        return float("inf"), float("inf"), False

    # Exact match covers +/-inf and zero.
    if expected == actual:
        return 0.0, 0.0, True

    # One is inf and the other is not (or different sign).
    if math.isinf(expected) or math.isinf(actual):
        return float("inf"), float("inf"), False

    abs_err = abs(expected - actual)
    # Relative error: guard against division by zero.
    if expected == 0.0:
        rel_err = abs_err  # degenerate -- use absolute error as proxy
    else:
        rel_err = abs_err / abs(expected)

    ok = abs_err <= atol + rtol * abs(expected)
    return abs_err, rel_err, ok


def _format_value(v: float) -> str | float:
    """Return a JSON-friendly representation of *v*."""
    if math.isnan(v):
        return "NaN"
    if math.isinf(v):
        return "Infinity" if v > 0 else "-Infinity"
    return v

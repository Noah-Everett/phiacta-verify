"""Distribution equivalence comparison via summary statistics.

Since ``scipy`` is not available in the verification service, this module
implements a pure-Python approach: compare five summary statistics
(mean, standard deviation, minimum, maximum, median) of the expected and
actual distributions.  A normalised deviation is computed for each statistic
and the overall score is ``1 - max(deviations)``.

An optional Kolmogorov-Smirnov-style maximum-CDF-difference metric is also
computed (pure Python, no external libraries) and included in the details
but does not currently influence the pass/fail decision.
"""

from __future__ import annotations

import json
import math
import re
from typing import Sequence

from phiacta_verify.comparators.base import BaseComparator, ComparisonResult
from phiacta_verify.models.enums import ComparisonMethod

_DEFAULT_SIGNIFICANCE: float = 0.05

# Same number regex used by the numerical comparator.
_NUMBER_RE = re.compile(
    r"[+-]?"
    r"(?:"
    r"inf(?:inity)?"
    r"|nan"
    r"|(?:\d+\.?\d*|\.\d+)(?:[eEdD][+-]?\d+)?"
    r")",
    re.IGNORECASE,
)


class StatisticalComparator(BaseComparator):
    """Compare expected and actual outputs as numeric distributions.

    Numbers are extracted using the same strategy as
    :class:`~phiacta_verify.comparators.numerical.NumericalComparator`.
    NaN and infinite values are silently dropped before computing statistics.

    The comparison passes when the normalised deviation of every summary
    statistic (mean, std, min, max, median) is below the configured
    significance level.

    Keyword arguments accepted by :meth:`compare`:
        significance_level (float): Maximum allowed normalised deviation
            for each summary statistic.  Default ``0.05``.
    """

    def compare(self, expected: bytes, actual: bytes, **kwargs) -> ComparisonResult:
        significance: float = kwargs.get("significance_level", _DEFAULT_SIGNIFICANCE)

        expected_values = _parse_finite_numbers(expected)
        actual_values = _parse_finite_numbers(actual)

        details: dict = {}

        # Degenerate: no data in either side.
        if not expected_values and not actual_values:
            return ComparisonResult(
                matched=True,
                method=ComparisonMethod.STATISTICAL,
                score=1.0,
                details={"note": "both outputs produced no finite numbers"},
            )

        # One side empty, the other not.
        if not expected_values or not actual_values:
            return ComparisonResult(
                matched=False,
                method=ComparisonMethod.STATISTICAL,
                score=0.0,
                details={
                    "note": "one output produced no finite numbers",
                    "expected_count": len(expected_values),
                    "actual_count": len(actual_values),
                },
            )

        # Compute summary statistics.
        exp_stats = _summary(expected_values)
        act_stats = _summary(actual_values)

        details["count_expected"] = len(expected_values)
        details["count_actual"] = len(actual_values)

        max_deviation: float = 0.0
        deviations: dict[str, float] = {}

        for stat_name in ("mean", "std", "min", "max", "median"):
            exp_val = exp_stats[stat_name]
            act_val = act_stats[stat_name]
            details[f"{stat_name}_expected"] = exp_val
            details[f"{stat_name}_actual"] = act_val
            dev = _normalised_deviation(exp_val, act_val)
            deviations[stat_name] = dev
            max_deviation = max(max_deviation, dev)

        details["deviations"] = deviations
        details["max_deviation"] = max_deviation

        # Pure-Python KS statistic (informational).
        ks_stat = _ks_statistic(expected_values, actual_values)
        details["ks_statistic"] = ks_stat

        matched = max_deviation <= significance

        # Score: 1 - max_deviation, clamped.
        if math.isinf(max_deviation) or math.isnan(max_deviation):
            score = 0.0
        else:
            score = max(0.0, min(1.0, 1.0 - max_deviation))

        return ComparisonResult(
            matched=matched,
            method=ComparisonMethod.STATISTICAL,
            score=score,
            details=details,
        )


# ---------------------------------------------------------------------------
# Statistics helpers (pure Python, no numpy/scipy)
# ---------------------------------------------------------------------------


def _summary(values: Sequence[float]) -> dict[str, float]:
    """Compute mean, std, min, max, and median of *values*."""
    n = len(values)
    assert n > 0

    mean = math.fsum(values) / n
    min_val = min(values)
    max_val = max(values)

    # Population standard deviation (not sample -- consistent with numpy default).
    variance = math.fsum((x - mean) ** 2 for x in values) / n
    std = math.sqrt(variance)

    sorted_vals = sorted(values)
    if n % 2 == 1:
        median = sorted_vals[n // 2]
    else:
        median = (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0

    return {
        "mean": mean,
        "std": std,
        "min": min_val,
        "max": max_val,
        "median": median,
    }


def _normalised_deviation(expected: float, actual: float) -> float:
    """Compute a normalised deviation between two scalar statistics.

    Uses ``|expected - actual| / max(|expected|, |actual|, 1)`` so that
    the result is dimensionless and well-defined even when both values
    are zero.
    """
    if expected == actual:
        return 0.0
    diff = abs(expected - actual)
    scale = max(abs(expected), abs(actual), 1.0)
    return diff / scale


def _ks_statistic(a: Sequence[float], b: Sequence[float]) -> float:
    """Compute the two-sample Kolmogorov-Smirnov statistic.

    This is the maximum absolute difference between the empirical CDFs of
    *a* and *b*.  Pure Python, O(n log n + m log m).
    """
    sorted_a = sorted(a)
    sorted_b = sorted(b)
    na = len(sorted_a)
    nb = len(sorted_b)

    # Merge the two sorted arrays and walk them simultaneously.
    ia = 0
    ib = 0
    max_diff: float = 0.0

    while ia < na and ib < nb:
        if sorted_a[ia] < sorted_b[ib]:
            ia += 1
        elif sorted_b[ib] < sorted_a[ia]:
            ib += 1
        else:
            # Equal values -- advance both pointers.
            ia += 1
            ib += 1
        cdf_a = ia / na
        cdf_b = ib / nb
        diff = abs(cdf_a - cdf_b)
        if diff > max_diff:
            max_diff = diff

    return max_diff


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_finite_numbers(data: bytes) -> list[float]:
    """Extract finite numbers from *data*, dropping NaN and infinity."""
    text = data.decode("utf-8", errors="replace")

    values: list[float] = []

    # Try JSON first.
    try:
        obj = json.loads(text)
        _collect_json_numbers(obj, values)
        if values:
            return [v for v in values if math.isfinite(v)]
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: regex scan.
    for m in _NUMBER_RE.finditer(text):
        try:
            token = re.sub(r"[dD]", "e", m.group())
            v = float(token)
            if math.isfinite(v):
                values.append(v)
        except ValueError:
            continue

    return values


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

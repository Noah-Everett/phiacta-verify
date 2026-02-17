"""Tests for output comparators."""

from __future__ import annotations

import math

import pytest

from phiacta_verify.comparators.base import BaseComparator, ComparisonResult
from phiacta_verify.comparators.exact import ExactComparator
from phiacta_verify.comparators.image import ImageComparator
from phiacta_verify.comparators.numerical import NumericalComparator
from phiacta_verify.comparators.statistical import StatisticalComparator
from phiacta_verify.comparators import get_comparator
from phiacta_verify.models.enums import ComparisonMethod


# ======================================================================
# Factory
# ======================================================================


class TestGetComparator:
    """Tests for the get_comparator factory function."""

    @pytest.mark.parametrize(
        "method, expected_cls",
        [
            (ComparisonMethod.EXACT, ExactComparator),
            (ComparisonMethod.NUMERICAL_TOLERANCE, NumericalComparator),
            (ComparisonMethod.STATISTICAL, StatisticalComparator),
            (ComparisonMethod.PERCEPTUAL_HASH, ImageComparator),
        ],
    )
    def test_returns_correct_class(
        self, method: ComparisonMethod, expected_cls: type[BaseComparator]
    ) -> None:
        comparator = get_comparator(method)
        assert isinstance(comparator, expected_cls)

    def test_unknown_method_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown comparison method"):
            get_comparator("NONEXISTENT")  # type: ignore[arg-type]


# ======================================================================
# ExactComparator
# ======================================================================


class TestExactComparator:
    """Tests for ExactComparator."""

    def setup_method(self) -> None:
        self.cmp = ExactComparator()

    # --- text mode ---

    def test_identical_text(self) -> None:
        r = self.cmp.compare(b"hello world\n", b"hello world\n")
        assert r.matched is True
        assert r.score == 1.0
        assert r.method == ComparisonMethod.EXACT
        assert r.details["mode"] == "text"

    def test_trailing_whitespace_ignored(self) -> None:
        r = self.cmp.compare(b"hello world  \n\n", b"hello world\n")
        assert r.matched is True
        assert r.score == 1.0

    def test_trailing_newlines_ignored(self) -> None:
        r = self.cmp.compare(b"abc\n\n\n", b"abc")
        assert r.matched is True

    def test_different_text(self) -> None:
        r = self.cmp.compare(b"hello", b"world")
        assert r.matched is False
        assert r.score == 0.0

    def test_empty_inputs(self) -> None:
        r = self.cmp.compare(b"", b"")
        assert r.matched is True
        assert r.score == 1.0

    def test_one_empty(self) -> None:
        r = self.cmp.compare(b"data", b"")
        assert r.matched is False

    def test_multiline_whitespace(self) -> None:
        expected = b"line1  \nline2\t\nline3   \n\n"
        actual = b"line1\nline2\nline3"
        r = self.cmp.compare(expected, actual)
        assert r.matched is True

    # --- binary mode ---

    def test_binary_identical(self) -> None:
        data = b"\x80\x81\x82\xff"
        r = self.cmp.compare(data, data)
        assert r.matched is True
        assert r.details["mode"] == "binary"

    def test_binary_different(self) -> None:
        r = self.cmp.compare(b"\x80\x81\x82", b"\x80\x81\x83")
        assert r.matched is False
        assert r.details["mode"] == "binary"

    # --- details ---

    def test_details_byte_lengths(self) -> None:
        r = self.cmp.compare(b"abc", b"abcdef")
        assert r.details["byte_length_expected"] == 3
        assert r.details["byte_length_actual"] == 6


# ======================================================================
# NumericalComparator
# ======================================================================


class TestNumericalComparator:
    """Tests for NumericalComparator."""

    def setup_method(self) -> None:
        self.cmp = NumericalComparator()

    # --- exact numeric match ---

    def test_identical_one_per_line(self) -> None:
        r = self.cmp.compare(b"1.0\n2.0\n3.0\n", b"1.0\n2.0\n3.0\n")
        assert r.matched is True
        assert r.score == 1.0
        assert r.method == ComparisonMethod.NUMERICAL_TOLERANCE

    def test_identical_json_array(self) -> None:
        r = self.cmp.compare(b"[1.0, 2.0, 3.0]", b"[1.0, 2.0, 3.0]")
        assert r.matched is True

    def test_identical_csv(self) -> None:
        r = self.cmp.compare(b"1.0,2.0,3.0", b"1.0,2.0,3.0")
        assert r.matched is True

    # --- within tolerance ---

    def test_within_default_tolerance(self) -> None:
        r = self.cmp.compare(b"1.0", b"1.0000000001")
        assert r.matched is True

    def test_custom_tolerance_accepts(self) -> None:
        r = self.cmp.compare(b"1.0", b"1.1", rtol=0.2, atol=0.0)
        assert r.matched is True

    def test_custom_tolerance_rejects(self) -> None:
        r = self.cmp.compare(b"1.0", b"1.1", rtol=0.01, atol=0.0)
        assert r.matched is False

    # --- special values ---

    def test_nan_matches_nan(self) -> None:
        r = self.cmp.compare(b"nan", b"nan")
        assert r.matched is True

    def test_nan_does_not_match_number(self) -> None:
        r = self.cmp.compare(b"nan", b"1.0")
        assert r.matched is False

    def test_inf_matches_inf(self) -> None:
        r = self.cmp.compare(b"inf", b"inf")
        assert r.matched is True

    def test_neg_inf_matches_neg_inf(self) -> None:
        r = self.cmp.compare(b"-inf", b"-inf")
        assert r.matched is True

    def test_inf_does_not_match_neg_inf(self) -> None:
        r = self.cmp.compare(b"inf", b"-inf")
        assert r.matched is False

    def test_mixed_special_values(self) -> None:
        r = self.cmp.compare(b"nan\ninf\n-inf\n", b"nan\ninf\n-inf\n")
        assert r.matched is True

    # --- scientific notation ---

    def test_scientific_notation(self) -> None:
        r = self.cmp.compare(b"1.23e-4", b"1.23e-4")
        assert r.matched is True

    def test_fortran_notation(self) -> None:
        r = self.cmp.compare(b"1.23D+02", b"123.0")
        assert r.matched is True

    # --- mismatches ---

    def test_value_mismatch(self) -> None:
        r = self.cmp.compare(b"1.0,2.0,3.0", b"1.0,2.0,3.5")
        assert r.matched is False
        assert len(r.details["mismatches"]) >= 1

    def test_length_mismatch(self) -> None:
        r = self.cmp.compare(b"1.0\n2.0", b"1.0\n2.0\n3.0")
        assert r.matched is False
        assert r.score == 0.0

    # --- edge cases ---

    def test_no_numbers(self) -> None:
        r = self.cmp.compare(b"no numbers here", b"also no numbers")
        assert r.matched is True
        assert r.score == 1.0
        assert r.details["values_compared"] == 0

    def test_score_between_0_and_1(self) -> None:
        # Small mismatch: score should be between 0 and 1
        r = self.cmp.compare(b"1.0", b"1.05", rtol=0.01, atol=0.0)
        assert 0.0 <= r.score <= 1.0

    # --- details structure ---

    def test_details_keys(self) -> None:
        r = self.cmp.compare(b"1.0\n2.0", b"1.0\n2.0")
        assert "max_relative_error" in r.details
        assert "max_absolute_error" in r.details
        assert "values_compared" in r.details
        assert "mismatches" in r.details
        assert r.details["values_compared"] == 2
        assert r.details["mismatches"] == []


# ======================================================================
# StatisticalComparator
# ======================================================================


class TestStatisticalComparator:
    """Tests for StatisticalComparator."""

    def setup_method(self) -> None:
        self.cmp = StatisticalComparator()

    def test_identical_distributions(self) -> None:
        r = self.cmp.compare(b"1\n2\n3\n4\n5", b"1\n2\n3\n4\n5")
        assert r.matched is True
        assert r.score == 1.0
        assert r.method == ComparisonMethod.STATISTICAL

    def test_slight_shift_matches(self) -> None:
        r = self.cmp.compare(
            b"1\n2\n3\n4\n5", b"1.01\n2.01\n3.01\n4.01\n5.01"
        )
        assert r.matched is True

    def test_large_shift_fails(self) -> None:
        r = self.cmp.compare(b"1\n2\n3", b"100\n200\n300")
        assert r.matched is False

    def test_both_empty(self) -> None:
        r = self.cmp.compare(b"no numbers", b"no numbers")
        assert r.matched is True

    def test_one_empty(self) -> None:
        r = self.cmp.compare(b"1\n2\n3", b"no numbers")
        assert r.matched is False
        assert r.score == 0.0

    def test_custom_significance_tight(self) -> None:
        r = self.cmp.compare(
            b"1\n2\n3", b"1.05\n2.05\n3.05", significance_level=0.001
        )
        assert r.matched is False

    def test_custom_significance_loose(self) -> None:
        r = self.cmp.compare(
            b"1\n2\n3", b"1.05\n2.05\n3.05", significance_level=0.1
        )
        assert r.matched is True

    # --- details structure ---

    def test_details_summary_stats(self) -> None:
        r = self.cmp.compare(b"1\n2\n3\n4\n5", b"1\n2\n3\n4\n5")
        d = r.details
        assert d["mean_expected"] == 3.0
        assert d["mean_actual"] == 3.0
        assert d["median_expected"] == 3.0
        assert d["min_expected"] == 1.0
        assert d["max_expected"] == 5.0
        assert "std_expected" in d
        assert "std_actual" in d

    def test_details_ks_statistic(self) -> None:
        r = self.cmp.compare(b"1\n2\n3\n4\n5", b"1\n2\n3\n4\n5")
        assert "ks_statistic" in r.details
        assert r.details["ks_statistic"] == 0.0

    def test_details_deviations(self) -> None:
        r = self.cmp.compare(b"1\n2\n3\n4\n5", b"1\n2\n3\n4\n5")
        assert "deviations" in r.details
        assert "max_deviation" in r.details
        for stat in ("mean", "std", "min", "max", "median"):
            assert stat in r.details["deviations"]

    def test_ks_nonzero_for_different_distributions(self) -> None:
        r = self.cmp.compare(
            b"1\n2\n3\n4\n5",
            b"10\n20\n30\n40\n50",
        )
        assert r.details["ks_statistic"] > 0.0

    def test_json_input(self) -> None:
        r = self.cmp.compare(
            b"[1, 2, 3, 4, 5]",
            b"[1, 2, 3, 4, 5]",
        )
        assert r.matched is True

    def test_nan_and_inf_are_dropped(self) -> None:
        # NaN and inf should be dropped; only finite values compared
        r = self.cmp.compare(
            b"1\n2\n3\nnan\ninf",
            b"1\n2\n3",
        )
        assert r.matched is True

    def test_score_clamped(self) -> None:
        r = self.cmp.compare(b"1\n2\n3", b"100\n200\n300")
        assert 0.0 <= r.score <= 1.0


# ======================================================================
# ImageComparator
# ======================================================================


class TestImageComparator:
    """Tests for ImageComparator."""

    def setup_method(self) -> None:
        self.cmp = ImageComparator()

    def test_identical_data(self) -> None:
        data = b"\x89PNG\r\n" + bytes(range(256)) * 4
        r = self.cmp.compare(data, data)
        assert r.matched is True
        assert r.score == 1.0
        assert r.method == ComparisonMethod.PERCEPTUAL_HASH

    def test_one_byte_diff(self) -> None:
        data = b"\x89PNG\r\n" + bytes(range(256)) * 4
        data2 = bytearray(data)
        data2[10] = (data2[10] + 1) % 256
        r = self.cmp.compare(data, bytes(data2))
        # Only 1 byte out of 1030 differs -- should pass at 0.95
        assert r.matched is True
        assert r.score > 0.99

    def test_completely_different(self) -> None:
        r = self.cmp.compare(b"\x00" * 100, b"\xff" * 100)
        assert r.matched is False
        assert r.score == 0.0

    def test_different_lengths(self) -> None:
        r = self.cmp.compare(b"\x00" * 100, b"\x00" * 50)
        assert r.score == pytest.approx(0.5)

    def test_both_empty(self) -> None:
        r = self.cmp.compare(b"", b"")
        assert r.matched is True
        assert r.score == 1.0

    def test_custom_threshold_low(self) -> None:
        r = self.cmp.compare(b"\x00" * 100, b"\x00" * 50, threshold=0.4)
        assert r.matched is True

    def test_custom_threshold_high(self) -> None:
        data = b"\x89PNG" + bytes(range(256))
        data2 = bytearray(data)
        data2[5] = (data2[5] + 1) % 256
        r = self.cmp.compare(data, bytes(data2), threshold=0.9999)
        assert r.matched is False

    # --- details structure ---

    def test_details_hashes(self) -> None:
        r = self.cmp.compare(b"abc", b"abd")
        assert "hash_expected" in r.details
        assert "hash_actual" in r.details
        assert r.details["hash_expected"] != r.details["hash_actual"]

    def test_details_sizes(self) -> None:
        r = self.cmp.compare(b"abc", b"abcdef")
        assert r.details["size_expected"] == 3
        assert r.details["size_actual"] == 6

    def test_details_byte_counts(self) -> None:
        r = self.cmp.compare(b"\x00\x01\x02", b"\x00\x01\x03")
        assert r.details["bytes_total"] == 3
        assert r.details["bytes_matching"] == 2
        assert r.details["similarity"] == pytest.approx(2 / 3)

    def test_identical_hash_fast_path(self) -> None:
        data = b"test data for hashing"
        r = self.cmp.compare(data, data)
        assert r.details["hash_expected"] == r.details["hash_actual"]
        assert r.details["similarity"] == 1.0


# ======================================================================
# ComparisonResult
# ======================================================================


class TestComparisonResult:
    """Tests for the ComparisonResult dataclass."""

    def test_defaults(self) -> None:
        r = ComparisonResult(matched=True, method=ComparisonMethod.EXACT, score=1.0)
        assert r.details == {}

    def test_custom_details(self) -> None:
        r = ComparisonResult(
            matched=False,
            method=ComparisonMethod.EXACT,
            score=0.0,
            details={"key": "value"},
        )
        assert r.details == {"key": "value"}

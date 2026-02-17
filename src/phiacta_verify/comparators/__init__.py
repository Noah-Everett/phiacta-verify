"""Output comparators for verification jobs.

Public API:

* :class:`ComparisonResult` -- data-class returned by every comparator.
* :class:`BaseComparator` -- abstract base class.
* :class:`ExactComparator`
* :class:`NumericalComparator`
* :class:`StatisticalComparator`
* :class:`ImageComparator`
* :func:`get_comparator` -- factory that maps a
  :class:`~phiacta_verify.models.enums.ComparisonMethod` to its
  concrete comparator instance.
"""

from __future__ import annotations

from phiacta_verify.comparators.base import BaseComparator, ComparisonResult
from phiacta_verify.comparators.exact import ExactComparator
from phiacta_verify.comparators.image import ImageComparator
from phiacta_verify.comparators.numerical import NumericalComparator
from phiacta_verify.comparators.statistical import StatisticalComparator
from phiacta_verify.models.enums import ComparisonMethod

__all__ = [
    "BaseComparator",
    "ComparisonResult",
    "ExactComparator",
    "ImageComparator",
    "NumericalComparator",
    "StatisticalComparator",
    "get_comparator",
]

_COMPARATOR_MAP: dict[ComparisonMethod, type[BaseComparator]] = {
    ComparisonMethod.EXACT: ExactComparator,
    ComparisonMethod.NUMERICAL_TOLERANCE: NumericalComparator,
    ComparisonMethod.STATISTICAL: StatisticalComparator,
    ComparisonMethod.PERCEPTUAL_HASH: ImageComparator,
}


def get_comparator(method: ComparisonMethod) -> BaseComparator:
    """Return a comparator instance for the given *method*.

    Raises:
        ValueError: If *method* is not a recognised
            :class:`~phiacta_verify.models.enums.ComparisonMethod`.
    """
    cls = _COMPARATOR_MAP.get(method)
    if cls is None:
        raise ValueError(
            f"Unknown comparison method {method!r}. "
            f"Supported methods: {', '.join(m.value for m in _COMPARATOR_MAP)}"
        )
    return cls()

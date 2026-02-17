"""Abstract comparator interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from phiacta_verify.models.enums import ComparisonMethod


@dataclass
class ComparisonResult:
    """Outcome of comparing expected vs actual output.

    Attributes:
        matched: Whether the comparison passed.
        method: The comparison method that was used.
        score: Similarity score between 0.0 (completely different)
               and 1.0 (identical).
        details: Method-specific diagnostic information.
    """

    matched: bool
    method: ComparisonMethod
    score: float  # 0.0 to 1.0
    details: dict = field(default_factory=dict)


class BaseComparator(ABC):
    """Base class for all output comparators.

    Subclasses must implement :meth:`compare`, which accepts expected and
    actual outputs as raw ``bytes`` and returns a :class:`ComparisonResult`.
    """

    @abstractmethod
    def compare(self, expected: bytes, actual: bytes, **kwargs) -> ComparisonResult:
        """Compare *expected* output against *actual* output.

        Parameters:
            expected: Reference output bytes.
            actual: Output bytes produced by the runner.
            **kwargs: Method-specific configuration (tolerances, thresholds, etc.).

        Returns:
            A :class:`ComparisonResult` describing the outcome.
        """
        ...

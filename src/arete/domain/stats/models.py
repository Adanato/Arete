"""
Domain models for FSRS statistics.

These are pure data structures with no I/O or external dependencies.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FsrsMemoryState:
    """
    FSRS memory state for a card.

    Attributes:
        stability: Days until recall probability drops to 90%.
        difficulty: Card difficulty (0.0-1.0 normalized from Anki's 1-10 scale).
        retrievability: Current probability of recall (0.0-1.0).
    """

    stability: float
    difficulty: float
    retrievability: float | None = None


@dataclass(frozen=True)
class ReviewEntry:
    """
    A single review log entry.

    Attributes:
        card_id: The card that was reviewed.
        review_time: Epoch timestamp of the review.
        rating: Button pressed (1=Again, 2=Hard, 3=Good, 4=Easy).
        interval: Interval assigned after this review (days).
        review_type: 0=learn, 1=review, 2=relearn, 3=early review.
    """

    card_id: int
    review_time: int
    rating: int
    interval: int
    review_type: int


@dataclass
class CardStatsAggregate:
    """
    Comprehensive statistics for a card, combining Anki data with FSRS metrics.

    This is the rich domain object used for analytics and dependency queue logic.
    """

    card_id: int
    note_id: int
    deck_name: str

    # Core Anki stats
    lapses: int
    ease: int  # SM-2 factor (e.g., 2500 = 250%)
    interval: int  # Current interval in days
    due: int  # Due date as epoch or day number
    reps: int  # Total review count

    # FSRS memory state (None if FSRS is not enabled or data unavailable)
    fsrs: FsrsMemoryState | None = None

    # Timing
    last_review: int | None = None  # Epoch of last review
    average_time_ms: int = 0  # Average review time in ms

    # Review history (populated on demand for derived metrics)
    reviews: list[ReviewEntry] = field(default_factory=list)

    # Content (for display purposes)
    front: str | None = None

"""
Metrics calculator for deriving insights from raw FSRS stats.

This is a pure computation module with no I/O.
"""

import time
from dataclasses import dataclass

from arete.domain.stats.models import CardStatsAggregate, ReviewEntry


@dataclass
class EnrichedStats:
    """
    Card stats enriched with computed metrics.
    """

    # Original aggregate
    card_id: int
    note_id: int
    deck_name: str
    lapses: int
    ease: int
    interval: int
    due: int
    reps: int
    front: str | None

    # FSRS core (from aggregate)
    stability: float | None
    difficulty: float | None

    # Computed metrics
    current_retrievability: float | None
    lapse_rate: float | None  # lapses / reps
    volatility: float | None  # Stability variance over recent reviews
    days_overdue: int | None  # Negative if not yet due


class MetricsCalculator:
    """
    Computes derived metrics from raw CardStatsAggregate objects.

    Stateless and side-effect free.
    """

    def enrich(self, card: CardStatsAggregate) -> EnrichedStats:
        """
        Enrich a card's stats with computed metrics.
        """
        retrievability = self._compute_retrievability(card)
        lapse_rate = self._compute_lapse_rate(card)
        volatility = self._compute_volatility(card.reviews)
        days_overdue = self._compute_days_overdue(card)

        return EnrichedStats(
            card_id=card.card_id,
            note_id=card.note_id,
            deck_name=card.deck_name,
            lapses=card.lapses,
            ease=card.ease,
            interval=card.interval,
            due=card.due,
            reps=card.reps,
            front=card.front,
            stability=card.fsrs.stability if card.fsrs else None,
            difficulty=card.fsrs.difficulty if card.fsrs else None,
            current_retrievability=retrievability,
            lapse_rate=lapse_rate,
            volatility=volatility,
            days_overdue=days_overdue,
        )

    def _compute_retrievability(self, card: CardStatsAggregate) -> float | None:
        """
        Compute current recall probability using FSRS formula.

        R = 0.9^(t/S) where t = days since last review, S = stability.
        """
        if not card.fsrs or not card.last_review:
            return None

        now_epoch = int(time.time())
        days_elapsed = (now_epoch - card.last_review) / 86400.0

        if card.fsrs.stability <= 0:
            return None

        return 0.9 ** (days_elapsed / card.fsrs.stability)

    def _compute_lapse_rate(self, card: CardStatsAggregate) -> float | None:
        """
        Compute lapse rate as lapses / total reviews.
        """
        if card.reps == 0:
            return None
        return card.lapses / card.reps

    def _compute_volatility(self, reviews: list[ReviewEntry]) -> float | None:
        """
        Compute variance in intervals over recent reviews.

        High volatility indicates unstable learning.
        """
        if len(reviews) < 3:
            return None

        # Use last 10 reviews
        recent = reviews[-10:]
        intervals = [r.interval for r in recent if r.interval > 0]

        if len(intervals) < 2:
            return None

        mean = sum(intervals) / len(intervals)
        variance = sum((i - mean) ** 2 for i in intervals) / len(intervals)
        return variance

    def _compute_days_overdue(self, card: CardStatsAggregate) -> int | None:
        """
        Compute days overdue (negative if not yet due).

        Note: Anki stores 'due' differently depending on card type.
        For review cards, it's the day number (days since collection created).
        We approximate using epoch comparison if available.
        """
        if not card.last_review or card.interval == 0:
            return None

        now_epoch = int(time.time())
        expected_due_epoch = card.last_review + (card.interval * 86400)
        return int((now_epoch - expected_due_epoch) / 86400)

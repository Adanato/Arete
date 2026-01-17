"""
FSRS Stats Service — Application layer orchestrator.

Coordinates fetching stats from the repository and enriching them with computed metrics.
"""

import logging

from arete.domain.stats.models import CardStatsAggregate
from arete.domain.stats.ports import StatsRepository

from .metrics_calculator import EnrichedStats, MetricsCalculator

logger = logging.getLogger(__name__)


class FsrsStatsService:
    """
    Application service for fetching and enriching card statistics.

    Follows Dependency Inversion: depends on StatsRepository abstraction,
    not concrete adapter implementations.
    """

    def __init__(
        self,
        stats_repo: StatsRepository,
        calculator: MetricsCalculator | None = None,
    ):
        """
        Args:
            stats_repo: The repository (port) for fetching stats.
            calculator: Optional custom calculator; uses default if not provided.
        """
        self._repo = stats_repo
        self._calc = calculator or MetricsCalculator()

    async def get_enriched_stats(self, nids: list[int]) -> list[EnrichedStats]:
        """
        Fetch stats for the given note IDs and enrich them with computed metrics.

        Args:
            nids: List of Anki note IDs.

        Returns:
            List of EnrichedStats with both raw and computed metrics.
        """
        if not nids:
            return []

        raw_stats = await self._repo.get_card_stats(nids)
        return [self._calc.enrich(card) for card in raw_stats]

    async def get_raw_stats(self, nids: list[int]) -> list[CardStatsAggregate]:
        """
        Fetch raw stats without enrichment.

        Useful when only basic data is needed.
        """
        if not nids:
            return []
        return await self._repo.get_card_stats(nids)

    async def get_weak_prerequisites(
        self,
        nids: list[int],
        stability_threshold: float = 7.0,
        lapse_threshold: int = 1,
    ) -> list[EnrichedStats]:
        """
        Identify cards that are "weak" based on configurable thresholds.

        A card is weak if:
        - stability < threshold, OR
        - lapses > 0 in recent reviews, OR
        - retrievability < 0.7

        Args:
            nids: Note IDs to check.
            stability_threshold: Stability below this is considered weak.
            lapse_threshold: Minimum lapses to be considered weak.

        Returns:
            List of EnrichedStats for weak cards.
        """
        enriched = await self.get_enriched_stats(nids)
        weak = []

        for card in enriched:
            is_weak = False

            # Low stability
            if card.stability is not None and card.stability < stability_threshold:
                is_weak = True

            # Has lapses
            if card.lapses >= lapse_threshold:
                is_weak = True

            # Low retrievability
            if (
                card.current_retrievability is not None
                and card.current_retrievability < 0.7
            ):
                is_weak = True

            if is_weak:
                weak.append(card)

        return weak

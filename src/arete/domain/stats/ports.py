"""
Ports (interfaces) for stats retrieval.

These define the contract that infrastructure adapters must implement.
Application services depend on these abstractions, not concrete implementations.
"""

from abc import ABC, abstractmethod

from .models import CardStatsAggregate, ReviewEntry


class StatsRepository(ABC):
    """
    Port for fetching card statistics from Anki.

    Implementations:
        - DirectStatsRepository: Queries Anki's SQLite database directly.
        - ConnectStatsRepository: Uses AnkiConnect HTTP API.
    """

    @abstractmethod
    async def get_card_stats(self, nids: list[int]) -> list[CardStatsAggregate]:
        """
        Fetch comprehensive stats for cards belonging to the given note IDs.

        Args:
            nids: List of Anki note IDs.

        Returns:
            List of CardStatsAggregate objects with FSRS data populated if available.
        """
        pass

    @abstractmethod
    async def get_review_history(self, cids: list[int]) -> list[ReviewEntry]:
        """
        Fetch review history for the given card IDs.

        Args:
            cids: List of Anki card IDs.

        Returns:
            List of ReviewEntry objects, sorted by review_time ascending.
        """
        pass

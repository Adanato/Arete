"""Ports (interfaces) for stats retrieval.

These define the contract that infrastructure adapters must implement.
Application services depend on these abstractions, not concrete implementations.
"""

from abc import ABC, abstractmethod

from .models import CardStatsAggregate, ReviewEntry


class StatsRepository(ABC):
    """Port for fetching card statistics from Anki.

    Implementations:
        - DirectStatsRepository: Queries Anki's SQLite database directly.
        - ConnectStatsRepository: Uses AnkiConnect HTTP API.
    """

    @abstractmethod
    async def get_card_stats(self, nids: list[int]) -> list[CardStatsAggregate]:
        """Fetch comprehensive stats for cards belonging to the given note IDs.

        Args:
            nids: List of Anki note IDs.

        Returns:
            List of CardStatsAggregate objects with FSRS data populated if available.

        """
        pass

    @abstractmethod
    async def get_review_history(self, cids: list[int]) -> list[ReviewEntry]:
        """Fetch review history for the given card IDs.

        Args:
            cids: List of Anki card IDs.

        Returns:
            List of ReviewEntry objects, sorted by review_time ascending.

        """
        pass

    @abstractmethod
    async def get_deck_params(self, deck_names: list[str]) -> dict[str, dict]:
        """Fetch FSRS parameters (desired retention, weights) for the given decks.

        Args:
            deck_names: List of deck names to fetch parameters for.

        Returns:
            Dictionary mapping deck names to their FSRS parameters.

        """
        pass

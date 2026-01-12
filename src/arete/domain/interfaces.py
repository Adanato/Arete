from abc import ABC, abstractmethod

from .models import AnkiDeck, UpdateItem, WorkItem


class AnkiBridge(ABC):
    """
    Abstract interface for Anki backend operations.

    Implementations (Adapters) are responsible for translating domain-level
    WorkItems into backend-specific commands (e.g., HTTP for AnkiConnect
    or SQLite/CLI for apy).
    """

    @abstractmethod
    async def sync_notes(self, work_items: list[WorkItem]) -> list[UpdateItem]:
        """
        Process a batch of notes: add new ones or update existing ones.

        If a note has an existing 'nid', the adapter should attempt to
        update the existing note. If no 'nid' is provided, it should create
         a new one.

        Note: AnkiConnect implementation additionally performs 'Self-Healing'
        by searching for duplicate content if creation fails.
        """
        pass

    @abstractmethod
    async def get_model_names(self) -> list[str]:
        """Return available model types currently installed in Anki."""
        pass

    @abstractmethod
    async def ensure_deck(self, deck: AnkiDeck | str) -> bool:
        """
        Ensure the named deck exists.
        Implementations should handle nested '::' hierarchies.
        """
        pass

    @abstractmethod
    async def get_deck_names(self) -> list[str]:
        """Return list of all deck names present in Anki."""
        pass

    @abstractmethod
    async def get_notes_in_deck(self, deck_name: str) -> dict[str, int]:
        """
        Return mapping of {obsidian_nid: anki_nid} for all notes in a deck.
        Used primarily by the Pruning stage to identify orphaned cards.
        """
        pass

    @abstractmethod
    async def delete_notes(self, nids: list[int]) -> bool:
        """Permanently delete specified note IDs from Anki."""
        pass

    @abstractmethod
    async def delete_decks(self, names: list[str]) -> bool:
        """Permanently delete specified decks (and their notes) from Anki."""
        pass

from dataclasses import dataclass
from pathlib import Path


@dataclass
class AnkiModel:
    """
    Represents an Anki Note Type (Model).
    """

    name: str
    fields: list[str]


@dataclass
class AnkiDeck:
    """
    Represents an Anki Deck.
    """

    name: str
    # Future extensibility: dynamic options, confusion flags, etc.

    @property
    def parents(self) -> list[str]:
        """Return all parent deck names in the '::' hierarchy."""
        parts = self.name.split("::")
        parents_list = []
        for i in range(1, len(parts)):
            parents_list.append("::".join(parts[:i]))
        return parents_list


@dataclass
class AnkiNote:
    """
    Represents a fully parsed Anki note ready to be sent to the backend.

    Attributes:
        model: The Anki model name (e.g., 'Basic', 'Cloze').
        deck: The destination deck name (supporting nested '::' syntax).
        fields: Mapping of Anki field names to HTML content (pre-rendered by Parser).
        tags: List of tags to associate with the note.
        start_line: First line of the card in the source Markdown.
        end_line: Last line of the card in the source Markdown.
        source_file: Path to the original Markdown file.
        source_index: 1-based index of this card within the source file.
        nid: Existing Note ID from Obsidian frontmatter (if any).
        cid: Existing Card ID from Obsidian frontmatter (if any).
        content_hash: MD5 hash of the fields/tags for cache-aware syncing.
    """

    model: str
    deck: str
    fields: dict[str, str]
    tags: list[str]
    start_line: int
    end_line: int

    source_file: Path
    source_index: int

    nid: str | None = None
    cid: str | None = None

    content_hash: str | None = None


@dataclass
class WorkItem:
    """Carries a note through the pipeline with metadata."""

    note: AnkiNote
    source_file: Path
    source_index: int  # card index in file (1-based)


@dataclass
class UpdateItem:
    """
    Result of an Anki backend operation. Returned by AnkiBridge implementation.

    Attributes:
        source_file: Identifies which file this result belongs to.
        source_index: Identifies which card in the file this result belongs to.
        new_nid: The Note ID assigned by Anki (string for consistency).
        new_cid: The Card ID assigned by Anki (string for consistency).
        ok: Whether the operation succeeded.
        error: Descriptive error message if ok is False.
        note: The original AnkiNote object (used for cache persistence).
    """

    source_file: Path
    source_index: int
    new_nid: str | None
    new_cid: str | None
    ok: bool
    error: str | None = None
    note: AnkiNote | None = None

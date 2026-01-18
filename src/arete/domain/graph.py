"""
Domain types for dependency graph.

These types represent the structure of card dependencies
without any persistence or resolution logic.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CardNode:
    """
    A node in the dependency graph representing a single card.

    Attributes:
        id: Stable Arete ID (e.g., arete_01JH8Y3ZK4QJ9W6E2N8F6M0P5R)
        title: Display name (typically the Front field or filename)
        file_path: Path to source markdown file
        line_number: Line number in source file for navigation
    """

    id: str
    title: str
    file_path: str
    line_number: int


@dataclass
class DependencyGraph:
    """
    Complete dependency graph for a vault.

    Nodes are cards, edges are requires/related relationships.
    """

    nodes: dict[str, CardNode] = field(default_factory=dict)
    requires: dict[str, list[str]] = field(default_factory=dict)  # id → [prereq ids]
    related: dict[str, list[str]] = field(default_factory=dict)  # id → [related ids]

    def add_node(self, node: CardNode) -> None:
        """Add a card node to the graph."""
        self.nodes[node.id] = node
        if node.id not in self.requires:
            self.requires[node.id] = []
        if node.id not in self.related:
            self.related[node.id] = []

    def add_requires(self, from_id: str, to_id: str) -> None:
        """Add a 'requires' edge: from_id requires to_id."""
        if from_id not in self.requires:
            self.requires[from_id] = []
        if to_id not in self.requires[from_id]:
            self.requires[from_id].append(to_id)

    def add_related(self, from_id: str, to_id: str) -> None:
        """Add a 'related' edge: from_id is related to to_id."""
        if from_id not in self.related:
            self.related[from_id] = []
        if to_id not in self.related[from_id]:
            self.related[from_id].append(to_id)

    def get_prerequisites(self, card_id: str) -> list[str]:
        """Get all direct prerequisites for a card."""
        return self.requires.get(card_id, [])

    def get_dependents(self, card_id: str) -> list[str]:
        """Get all cards that require this card (reverse lookup)."""
        return [
            cid for cid, prereqs in self.requires.items() if card_id in prereqs
        ]

    def get_related(self, card_id: str) -> list[str]:
        """Get all related cards."""
        return self.related.get(card_id, [])


@dataclass
class LocalGraphResult:
    """
    Result of a local graph query centered on a specific card.

    Used by the UI to render the dependency visualization.
    """

    center: CardNode
    prerequisites: list[CardNode]  # Upstream requires (depth-limited)
    dependents: list[CardNode]  # Downstream requires (depth-limited)
    related: list[CardNode]  # Related cards
    cycles: list[list[str]]  # Groups of co-requisite card IDs

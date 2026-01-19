"""
Queue builder for dependency-aware study sessions.

Builds ordered study queues by:
1. Walking requires edges backward from due cards
2. Filtering for weak prerequisites
3. Topologically sorting for proper learning order
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from arete.application.graph_resolver import build_graph, topological_sort
from arete.domain.graph import DependencyGraph

logger = logging.getLogger(__name__)


@dataclass
class WeakPrereqCriteria:
    """
    Criteria for determining if a prerequisite is "weak" and needs review.

    All thresholds are optional. If not set, that criterion is not checked.
    """

    min_stability: float | None = None  # FSRS stability threshold
    max_lapses: int | None = None  # Maximum lapse count
    min_reviews: int | None = None  # Minimum total reviews
    max_interval: int | None = None  # Maximum interval in days


def build_simple_queue(
    vault_root: Path,
    due_card_ids: list[str],
    depth: int = 2,
    max_cards: int = 50,
) -> "QueueBuildResult":
    """
    Build a simple study queue from due cards.

    MVP: Collects prerequisites up to depth, then topological sort.

    Args:
        vault_root: Path to the Obsidian vault
        due_card_ids: List of Arete IDs that are due for review
        depth: How many prerequisite levels to include
        max_cards: Maximum cards in queue

    Returns:
        QueueBuildResult with ordered queues and diagnostics
    """
    from arete.application.graph_resolver import build_graph, detect_cycles, topological_sort

    graph = build_graph(vault_root)

    # Collect all prerequisites for due cards
    all_prereqs: set[str] = set()
    missing_prereqs: list[str] = []

    for card_id in due_card_ids:
        prereqs = _collect_prereqs(graph, card_id, depth, set())
        for prereq_id in prereqs:
            if prereq_id in graph.nodes:
                all_prereqs.add(prereq_id)
        # Track unresolved refs
        for ref in graph.unresolved_refs.get(card_id, []):
            if ref not in missing_prereqs:
                missing_prereqs.append(ref)

    # Remove due cards from prereqs (they'll be in main queue)
    all_prereqs -= set(due_card_ids)

    # Limit size
    prereq_list = list(all_prereqs)
    if len(prereq_list) + len(due_card_ids) > max_cards:
        prereq_list = prereq_list[: max_cards - len(due_card_ids)]

    # Topological sort both queues
    prereq_queue = topological_sort(graph, prereq_list)
    main_queue = topological_sort(graph, due_card_ids)

    # Detect cycles
    cycles = detect_cycles(graph)

    return QueueBuildResult(
        prereq_queue=prereq_queue,
        main_queue=main_queue,
        skipped_strong=[],
        missing_prereqs=missing_prereqs,
        cycles=cycles,
    )


@dataclass
class QueueBuildResult:
    """Result of queue building operation."""

    prereq_queue: list[str]  # Weak prereqs to study first (topo sorted)
    main_queue: list[str]  # Original due cards (topo sorted)
    skipped_strong: list[str]  # Strong prereqs that were filtered out
    missing_prereqs: list[str]  # Referenced prereqs not found in graph
    cycles: list[list[str]]  # Co-requisite groups detected


def build_dependency_queue(
    vault_root: Path,
    due_card_ids: list[str],
    depth: int = 2,
    max_nodes: int = 50,
    include_related: bool = False,
    weak_criteria: WeakPrereqCriteria | None = None,
    card_stats: dict[str, dict] | None = None,
) -> QueueBuildResult:
    """
    Build a study queue that includes weak prerequisites before due cards.

    Args:
        vault_root: Path to the Obsidian vault
        due_card_ids: List of Arete IDs for cards due today
        depth: Maximum prerequisite hops to traverse (default: 2)
        max_nodes: Maximum total cards in queue (default: 50)
        include_related: Whether to include related cards (NOT IMPLEMENTED)
        weak_criteria: Criteria for filtering weak prerequisites
        card_stats: Optional dict of card_id -> stats for weakness filtering

    Returns:
        QueueBuildResult with ordered queues and diagnostics
    """
    if include_related:
        raise NotImplementedError(
            "Related card boost not yet implemented. "
            "Set include_related=False to use requires-only mode."
        )

    # Build graph from vault
    graph = build_graph(vault_root)

    # Collect all prerequisites up to depth
    all_prereqs: set[str] = set()

    # Collect unresolved refs from the graph (tracked during build_graph)
    missing_prereqs: list[str] = []
    for due_id in due_card_ids:
        for ref in graph.unresolved_refs.get(due_id, []):
            if ref not in missing_prereqs:
                missing_prereqs.append(ref)

    for due_id in due_card_ids:
        prereqs = _collect_prereqs(graph, due_id, depth, set())
        for prereq_id in prereqs:
            if prereq_id in graph.nodes:
                all_prereqs.add(prereq_id)
                # Also collect any unresolved refs from prereqs
                for ref in graph.unresolved_refs.get(prereq_id, []):
                    if ref not in missing_prereqs:
                        missing_prereqs.append(ref)

    # Remove the due cards themselves from prereqs
    all_prereqs -= set(due_card_ids)

    # Filter for weak prerequisites
    weak_prereqs: list[str] = []
    strong_prereqs: list[str] = []

    for prereq_id in all_prereqs:
        if _is_weak_prereq(prereq_id, weak_criteria, card_stats):
            weak_prereqs.append(prereq_id)
        else:
            strong_prereqs.append(prereq_id)

    # Cap at max_nodes (prioritize weakest if we have stats)
    if len(weak_prereqs) > max_nodes:
        if card_stats:
            # Sort by weakness (lower stability = weaker)
            weak_prereqs.sort(key=lambda x: card_stats.get(x, {}).get("stability", float("inf")))
        weak_prereqs = weak_prereqs[:max_nodes]

    # Topologically sort both queues
    prereq_queue = topological_sort(graph, weak_prereqs)
    main_queue = topological_sort(graph, due_card_ids)

    # Detect cycles in the combined set
    from arete.application.graph_resolver import detect_cycles

    cycles = detect_cycles(graph)

    return QueueBuildResult(
        prereq_queue=prereq_queue,
        main_queue=main_queue,
        skipped_strong=strong_prereqs,
        missing_prereqs=missing_prereqs,
        cycles=cycles,
    )


def _collect_prereqs(
    graph: DependencyGraph,
    card_id: str,
    depth: int,
    visited: set[str],
) -> set[str]:
    """
    Recursively collect prerequisites up to a given depth.
    """
    if depth <= 0 or card_id in visited:
        return set()

    visited.add(card_id)
    prereqs: set[str] = set()

    for prereq_id in graph.get_prerequisites(card_id):
        prereqs.add(prereq_id)
        prereqs.update(_collect_prereqs(graph, prereq_id, depth - 1, visited))

    return prereqs


def _is_weak_prereq(
    card_id: str,
    criteria: WeakPrereqCriteria | None,
    card_stats: dict[str, dict] | None,
) -> bool:
    """
    Determine if a prerequisite card is "weak" based on criteria.

    If no criteria or stats are provided, all prereqs are considered weak.
    """
    if criteria is None:
        return True  # No filtering, include all

    if card_stats is None or card_id not in card_stats:
        return True  # No stats, assume weak

    stats = card_stats[card_id]

    # Check each criterion
    if criteria.min_stability is not None:
        stability = stats.get("stability")
        if stability is not None and stability < criteria.min_stability:
            return True

    if criteria.max_lapses is not None:
        lapses = stats.get("lapses", 0)
        if lapses > criteria.max_lapses:
            return True

    if criteria.min_reviews is not None:
        reviews = stats.get("reps", 0)
        if reviews < criteria.min_reviews:
            return True

    if criteria.max_interval is not None:
        interval = stats.get("interval", 0)
        if interval < criteria.max_interval:
            return True

    return False  # Card is strong, skip it

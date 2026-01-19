"""
Graph resolver for building dependency graphs from vault files.

Parses YAML frontmatter to extract deps.requires and deps.related,
builds the full dependency graph, and provides traversal utilities.
"""

import logging
from graphlib import CycleError, TopologicalSorter
from pathlib import Path

from arete.application.utils.fs import iter_markdown_files
from arete.application.utils.text import parse_frontmatter
from arete.domain.graph import CardNode, DependencyGraph, LocalGraphResult

logger = logging.getLogger(__name__)


def build_graph(vault_root: Path) -> DependencyGraph:
    """
    Build a complete dependency graph from all markdown files in the vault.

    Scans for files with cards that have `id` and `deps` fields.

    Dependency references support two formats:
    - arete_XXX: Direct card ID lookup
    - basename: All cards in the file with that basename (e.g., "algebra" -> algebra.md)
    """
    graph = DependencyGraph()

    # First pass: collect all cards and build file index
    file_index: dict[str, list[str]] = {}  # basename -> list of card IDs
    pending_deps: list[tuple[str, list[str], list[str]]] = []  # (card_id, requires, related)

    for md_path in iter_markdown_files(vault_root):
        try:
            text = md_path.read_text(encoding="utf-8")
            meta, _ = parse_frontmatter(text)

            if not meta or "__yaml_error__" in meta:
                continue

            cards = meta.get("cards", [])
            if not isinstance(cards, list):
                continue

            # Get file basename for index
            basename = md_path.stem  # "algebra.md" -> "algebra"
            if basename not in file_index:
                file_index[basename] = []

            for card in cards:
                if not isinstance(card, dict):
                    continue

                card_id = card.get("id")
                if not card_id:
                    continue  # Skip cards without Arete ID

                # Extract title from Front field or use ID
                fields = card.get("fields", {})
                if isinstance(fields, dict):
                    title = fields.get("Front", card_id)
                else:
                    title = card_id

                # Get line number if available
                line_number = card.get("__line__", 1)

                node = CardNode(
                    id=card_id,
                    title=str(title)[:100],  # Truncate long titles
                    file_path=str(md_path),
                    line_number=line_number,
                )
                graph.add_node(node)

                # Add to file index
                file_index[basename].append(card_id)

                # Collect deps for second pass
                deps = card.get("deps", {})
                if isinstance(deps, dict):
                    requires = deps.get("requires", [])
                    related = deps.get("related", [])
                    if requires or related:
                        pending_deps.append(
                            (
                                card_id,
                                requires if isinstance(requires, list) else [],
                                related if isinstance(related, list) else [],
                            )
                        )

        except Exception as e:
            logger.warning(f"Failed to parse {md_path}: {e}")
            continue

    # Second pass: resolve references and add edges
    for card_id, requires, related in pending_deps:
        for ref in requires:
            if isinstance(ref, str):
                resolved = _resolve_reference(ref, card_id, file_index, graph)
                for target_id in resolved:
                    graph.add_requires(card_id, target_id)

        for ref in related:
            if isinstance(ref, str):
                resolved = _resolve_reference(ref, card_id, file_index, graph)
                for target_id in resolved:
                    graph.add_related(card_id, target_id)

    return graph


def _resolve_reference(
    ref: str,
    card_id: str,
    file_index: dict[str, list[str]],
    graph: DependencyGraph,
) -> list[str]:
    """
    Resolve a dependency reference to card ID(s).

    - arete_XXX: Direct card ID (returns single-element list if exists)
    - basename: All cards in that file (returns list of all card IDs)

    Tracks unresolved references in the graph.
    """
    if ref.startswith("arete_"):
        # Direct card ID lookup
        if ref in graph.nodes:
            return [ref]
        else:
            logger.warning(f"Dependency reference '{ref}' not found in graph")
            graph.add_unresolved(card_id, ref)
            return []
    else:
        # Note basename -> all cards in that file
        if ref in file_index:
            return file_index[ref]
        else:
            logger.warning(f"Dependency reference '{ref}' - no file with basename '{ref}' found")
            graph.add_unresolved(card_id, ref)
            return []


def get_local_graph(
    graph: DependencyGraph,
    card_id: str,
    depth: int = 2,
    max_nodes: int = 150,
) -> LocalGraphResult | None:
    """
    Get a local subgraph centered on a specific card.

    Args:
        graph: The full dependency graph
        card_id: Center card's Arete ID
        depth: Maximum depth to traverse (default: 2)
        max_nodes: Maximum nodes to include (default: 150)

    Returns:
        LocalGraphResult with prerequisites, dependents, and related cards,
        or None if card_id not found.
    """
    if card_id not in graph.nodes:
        return None

    center = graph.nodes[card_id]
    prereqs: set[str] = set()
    dependents: set[str] = set()
    related_ids: set[str] = set()

    # Walk prerequisites (backward along requires edges)
    def walk_prereqs(cid: str, current_depth: int) -> None:
        if current_depth > depth or len(prereqs) >= max_nodes:
            return
        for prereq_id in graph.get_prerequisites(cid):
            if len(prereqs) >= max_nodes:
                break
            if prereq_id not in prereqs and prereq_id in graph.nodes:
                prereqs.add(prereq_id)
                walk_prereqs(prereq_id, current_depth + 1)

    # Walk dependents (forward along requires edges)
    def walk_dependents(cid: str, current_depth: int) -> None:
        if current_depth > depth or len(dependents) >= max_nodes:
            return
        for dep_id in graph.get_dependents(cid):
            if len(dependents) >= max_nodes:
                break
            if dep_id not in dependents and dep_id in graph.nodes:
                dependents.add(dep_id)
                walk_dependents(dep_id, current_depth + 1)

    walk_prereqs(card_id, 1)
    walk_dependents(card_id, 1)

    # Get related (only direct, no traversal)
    for rel_id in graph.get_related(card_id):
        if rel_id in graph.nodes:
            related_ids.add(rel_id)

    # Detect cycles involving the center card
    cycles = detect_cycles_for_card(graph, card_id)

    return LocalGraphResult(
        center=center,
        prerequisites=[graph.nodes[pid] for pid in prereqs],
        dependents=[graph.nodes[did] for did in dependents],
        related=[graph.nodes[rid] for rid in related_ids],
        cycles=cycles,
    )


def detect_cycles(graph: DependencyGraph) -> list[list[str]]:
    """
    Detect all cycles in the requires graph.

    Returns a list of strongly connected components (cycles).
    Each cycle is a list of card IDs that form a co-requisite group.
    """
    # Build adjacency for TopologicalSorter
    sorter = TopologicalSorter[str]()

    for card_id in graph.nodes:
        prereqs = graph.get_prerequisites(card_id)
        # Filter to only existing nodes
        valid_prereqs = [p for p in prereqs if p in graph.nodes]
        sorter.add(card_id, *valid_prereqs)

    try:
        # If this succeeds, no cycles
        list(sorter.static_order())
        return []
    except CycleError as e:
        # e.args[1] contains the cycle
        if len(e.args) > 1 and isinstance(e.args[1], list):
            return [e.args[1]]
        return [[]]


def detect_cycles_for_card(graph: DependencyGraph, card_id: str) -> list[list[str]]:
    """
    Detect cycles that include a specific card.

    Uses DFS to find back edges from the card.
    """
    visited: set[str] = set()
    rec_stack: set[str] = set()
    cycles: list[list[str]] = []
    path: list[str] = []

    def dfs(cid: str) -> None:
        visited.add(cid)
        rec_stack.add(cid)
        path.append(cid)

        for prereq_id in graph.get_prerequisites(cid):
            if prereq_id not in graph.nodes:
                continue
            if prereq_id not in visited:
                dfs(prereq_id)
            elif prereq_id in rec_stack:
                # Found cycle - extract the cycle from path
                cycle_start = path.index(prereq_id)
                cycle = path[cycle_start:]
                if card_id in cycle and cycle not in cycles:
                    cycles.append(cycle.copy())

        path.pop()
        rec_stack.remove(cid)

    if card_id in graph.nodes:
        dfs(card_id)

    return cycles


def topological_sort(
    graph: DependencyGraph,
    card_ids: list[str],
) -> list[str]:
    """
    Topologically sort a subset of cards based on requires edges.

    Cards without prerequisites come first.
    If cycles exist, they are treated as a group (arbitrary order within).

    Args:
        graph: The dependency graph
        card_ids: Cards to sort

    Returns:
        Sorted list of card IDs (prerequisites before dependents)
    """
    # Filter to only requested cards that exist
    valid_ids = {cid for cid in card_ids if cid in graph.nodes}

    # Build subgraph for TopologicalSorter
    sorter = TopologicalSorter[str]()

    for card_id in valid_ids:
        prereqs = graph.get_prerequisites(card_id)
        # Only include prereqs that are in our subset
        valid_prereqs = [p for p in prereqs if p in valid_ids]
        sorter.add(card_id, *valid_prereqs)

    try:
        return list(sorter.static_order())
    except CycleError:
        # If there are cycles, fall back to partial ordering
        # Return in original order with a warning
        logger.warning("Cycle detected in card dependencies, using original order")
        return list(valid_ids)

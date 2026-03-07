"""Snapshot service for prerequisite-ordering analysis.

Produces a CSV joining graph depth with FSRS stats per card.
Run periodically to build a longitudinal dataset, then analyze
in a notebook to test whether prereq-first ordering strengthens
dependent cards.

Key hypothesis: again-rate should be flat across graph depths
(not increasing with depth as it would without prereq ordering).
"""

from __future__ import annotations

import csv
import io
import logging
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from arete.application.queue.graph_resolver import build_graph
from arete.domain.graph import DependencyGraph
from arete.domain.interfaces import AnkiBridge

logger = logging.getLogger(__name__)


@dataclass
class CardSnapshot:
    """Single card's snapshot data for analysis."""

    arete_id: str
    depth: int  # 0 = root (no prereqs), -1 = unreachable
    title: str
    file: str
    stability: float | None
    difficulty: float | None
    retrievability: float | None
    reps: int
    lapses: int
    interval: int
    again_rate: float | None  # lapses / reps


def compute_depths(graph: DependencyGraph) -> dict[str, int]:
    """BFS from root nodes (no prerequisites) to compute depth per card.

    Root nodes (depth 0) have no prerequisites.
    A card's depth = max depth among its prerequisites + 1.
    """
    depths: dict[str, int] = {}

    # Find roots: nodes with no prerequisites
    roots = [nid for nid in graph.nodes if not graph.get_prerequisites(nid)]

    # BFS — track max depth per node
    queue: deque[tuple[str, int]] = deque((r, 0) for r in roots)
    while queue:
        node_id, d = queue.popleft()
        if node_id in depths and depths[node_id] >= d:
            continue
        depths[node_id] = d
        for dep in graph.get_dependents(node_id):
            queue.append((dep, d + 1))

    return depths


async def take_snapshot(
    anki: AnkiBridge,
    vault_root: Path,
) -> list[CardSnapshot]:
    """Build a snapshot joining graph depth with FSRS stats.

    Steps:
        1. Build dependency graph from vault
        2. Compute depth per card via BFS from roots
        3. Find all arete-tagged notes in Anki
        4. Map NIDs → arete IDs, get stats
        5. Join depth + stats by arete ID
    """
    # 1. Build graph + depths
    graph = build_graph(vault_root)
    depths = compute_depths(graph)

    if not graph.nodes:
        logger.warning("No nodes in dependency graph")
        return []

    # 2. Find all arete notes in Anki
    all_nids = await anki.find_all_arete_nids()
    if not all_nids:
        logger.warning("No arete-tagged notes found in Anki")
        return []

    # 3. Map NIDs → arete IDs
    arete_ids = await anki.map_nids_to_arete_ids(all_nids)
    nid_to_arete = {nid: aid for nid, aid in zip(all_nids, arete_ids) if aid}

    # 4. Get stats for all NIDs
    raw_stats = await anki.get_card_stats(all_nids)
    stats_by_nid = {s.note_id: s for s in raw_stats}

    # 5. Join: only cards that exist in both graph and Anki
    snapshots = []
    for nid, arete_id in nid_to_arete.items():
        node = graph.nodes.get(arete_id)
        if node is None:
            continue

        s = stats_by_nid.get(nid)
        if s is None:
            continue

        depth = depths.get(arete_id, -1)
        again_rate = (s.lapses / s.reps) if s.reps > 0 else None

        snapshots.append(
            CardSnapshot(
                arete_id=arete_id,
                depth=depth,
                title=node.title,
                file=node.file_path,
                stability=None,  # Basic stats don't include FSRS stability
                difficulty=s.difficulty,
                retrievability=None,
                reps=s.reps,
                lapses=s.lapses,
                interval=s.interval,
                again_rate=again_rate,
            )
        )

    # Sort by depth for readability
    snapshots.sort(key=lambda x: (x.depth, x.arete_id))
    logger.info(f"Snapshot: {len(snapshots)} cards with depth + stats")
    return snapshots


def snapshots_to_csv(snapshots: list[CardSnapshot]) -> str:
    """Convert snapshots to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "arete_id",
            "depth",
            "title",
            "file",
            "stability",
            "difficulty",
            "retrievability",
            "reps",
            "lapses",
            "interval",
            "again_rate",
        ]
    )
    for s in snapshots:
        writer.writerow(
            [
                s.arete_id,
                s.depth,
                s.title,
                s.file,
                s.stability,
                s.difficulty,
                s.retrievability,
                s.reps,
                s.lapses,
                s.interval,
                f"{s.again_rate:.4f}" if s.again_rate is not None else "",
            ]
        )
    return output.getvalue()

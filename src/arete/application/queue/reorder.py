"""Queue session file for plugin-side reorder.

At queue build time, we write a session JSON containing:
- Algorithm mode ("prereq" or "dynamic")
- Graph edges (prereqs per card) for the queued cards
- Arete ID → CID mapping

The Anki plugin reads this file and either:
- prereq: strictly gates dependents until all prereqs are answered
- dynamic: flexibly reorders by prereq-fresh count (Kahn's sort)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from arete.domain.graph import DependencyGraph

logger = logging.getLogger(__name__)

SESSION_DIR = Path.home() / ".config" / "arete"
SESSION_FILE = SESSION_DIR / "queue_session.json"


def write_queue_session(
    graph: DependencyGraph,
    ordered_ids: list[str],
    arete_id_to_cid: dict[str, int],
    deck_name: str,
    algo: str = "dynamic",
) -> Path:
    """Write a queue session file for the Anki plugin to use.

    Args:
        graph: The dependency graph (used to extract edges for queued cards).
        ordered_ids: Arete IDs in queue order.
        arete_id_to_cid: Mapping of arete ID → Anki CID.
        deck_name: Name of the filtered deck.
        algo: Algorithm mode ("prereq" or "dynamic").

    Returns:
        Path to the written session file.

    """
    cards: dict[str, dict] = {}

    for aid in ordered_ids:
        cid = arete_id_to_cid.get(aid)
        if cid is None:
            continue

        prereqs = []
        if aid in graph.nodes:
            prereqs = graph.get_prerequisites(aid)

        cards[aid] = {
            "cid": cid,
            "prereqs": prereqs,
        }

    session = {
        "algo": algo,
        "deck_name": deck_name,
        "queue_order": ordered_ids,
        "cards": cards,
    }

    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(session, indent=2))
    logger.info(f"Queue session written: {len(cards)} cards → {SESSION_FILE}")
    return SESSION_FILE


def clear_queue_session() -> None:
    """Remove the session file (e.g., after queue deck is emptied)."""
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()

"""Service for managing stable Arete IDs for cards."""

import logging
from pathlib import Path
from typing import Any

from ulid import ULID

from arete.application.utils.fs import iter_markdown_files
from arete.application.utils.text import (
    parse_frontmatter,
    rebuild_markdown_with_frontmatter,
    scrub_internal_keys,
)

logger = logging.getLogger(__name__)


def generate_arete_id() -> str:
    """Generate a stable Arete ID using ULID."""
    return f"arete_{ULID()}"


def assign_arete_ids(vault_root: Path, dry_run: bool = False) -> int:
    """
    Scans the vault and ensures every card has a stable Arete ID.
    Returns the number of IDs assigned.
    """
    ids_assigned = 0
    scanned = 0

    for file_path in iter_markdown_files(vault_root):
        scanned += 1
        content = file_path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(content)

        if not meta or "cards" not in meta:
            continue

        cards = meta.get("cards", [])
        if not isinstance(cards, list):
            continue

        modified = False
        for card in cards:
            if not isinstance(card, dict):
                continue

            if "id" not in card:
                card["id"] = generate_arete_id()
                modified = True
                ids_assigned += 1

        if modified:
            if not dry_run:
                # Use scrub_internal_keys to remove __line__ etc. before dumping
                normalized = rebuild_markdown_with_frontmatter(meta, body)
                file_path.write_text(normalized, encoding="utf-8")
                logger.info(f"Assigned IDs in {file_path}")
            else:
                logger.info(f"[DRY RUN] Would assign IDs in {file_path}")

    return ids_assigned

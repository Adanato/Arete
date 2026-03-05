"""Migration helpers: upgrade legacy frontmatter and normalize card schema."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from arete.domain.constants import ANKI_LEGACY_KEYS, CARD_KEY_ORDER


def _merge_split_cards(cards: list[Any]) -> list[Any]:
    """Merge cards that were accidentally split into two list items.

    Recombine Front and Back into one card if possible.
    """
    if not cards or len(cards) < 2:
        return cards

    new_cards: list[Any] = []
    i = 0
    while i < len(cards):
        curr = cards[i]

        # Look ahead for a potential split partner
        if i + 1 < len(cards):
            nxt = cards[i + 1]
            if isinstance(curr, dict) and isinstance(nxt, dict):
                has_front = any(k in curr for k in ("Front", "front", "Text", "text"))
                has_back = any(k in curr for k in ("Back", "back", "Extra", "extra"))
                next_has_front = any(k in nxt for k in ("Front", "front", "Text", "text"))
                next_has_back = any(k in nxt for k in ("Back", "back", "Extra", "extra"))

                # Case: Current has Front, next has Back (Standard split)
                if has_front and not has_back and next_has_back and not next_has_front:
                    # Merge them!
                    merged = {**curr, **nxt}
                    new_cards.append(merged)
                    i += 2
                    continue

        new_cards.append(curr)
        i += 1

    return new_cards


def _ensure_deps_block(card: dict) -> None:
    """Ensure card has a complete deps block with requires and related lists."""
    if "deps" not in card:
        card["deps"] = {"requires": [], "related": []}
    elif isinstance(card.get("deps"), dict):
        card["deps"].setdefault("requires", [])
        card["deps"].setdefault("related", [])


def _restructure_anki_fields(card: dict) -> None:
    """Move legacy nid/cid keys into a nested 'anki' block."""
    anki_block = card.get("anki", {})
    if not isinstance(anki_block, dict):
        anki_block = {}

    has_anki_data = bool(anki_block)
    for k in ANKI_LEGACY_KEYS:
        if k in card:
            anki_block[k] = card.pop(k)
            has_anki_data = True
    if has_anki_data:
        card["anki"] = anki_block


def _order_card_keys(card: dict) -> None:
    """Reorder card keys to a consistent preferred order."""
    ordered: dict = {}
    for key in CARD_KEY_ORDER:
        if key in card:
            ordered[key] = card.pop(key)
    for key in list(card.keys()):
        if not key.startswith("__"):
            ordered[key] = card.pop(key)
    for key in list(card.keys()):
        ordered[key] = card[key]
    card.clear()
    card.update(ordered)


def _enforce_card_v2_schema(card: dict) -> None:
    """Enforce V2 schema on a single card dict (deps, anki block, key order)."""
    _ensure_deps_block(card)
    _restructure_anki_fields(card)
    _order_card_keys(card)


def _strip_redundant_frontmatter(body: str, parse_frontmatter_fn: Any) -> str:
    """Strip redundant --- blocks that appear after the real frontmatter."""
    while body.lstrip().startswith("---"):
        stripped = body.lstrip()
        _, next_body = parse_frontmatter_fn(stripped)
        if next_body == stripped:
            lines = stripped.split("\n", 1)
            body = lines[1] if len(lines) > 1 else ""
        else:
            body = next_body
    return body


def _upgrade_to_arete(meta: dict) -> bool:
    """Upgrade legacy flags and return True if this is an arete note."""
    if "anki_template_version" in meta:
        val = meta.pop("anki_template_version")
        if str(val).strip() == "1":
            meta["arete"] = True
    return meta.get("arete") is True


def _heal_cards(meta: dict) -> None:
    """Merge split cards and enforce V2 schema on all card dicts."""
    if "cards" not in meta or not isinstance(meta["cards"], list):
        return
    meta["cards"] = _merge_split_cards(meta["cards"])
    for card in meta["cards"]:
        if isinstance(card, dict):
            _enforce_card_v2_schema(card)


def _migrate_single_file(
    p: Path, config: Any, ensure_card_ids: Any, text_utils: dict
) -> str | None:
    """Migrate a single file, returning new content or None to skip.

    Parameters
    ----------
    p : Path
        Path to the markdown file.
    config : AppConfig
        Application configuration (uses ``verbose`` attribute).
    ensure_card_ids : callable
        Function that assigns missing arete IDs to cards in *meta*.
    text_utils : dict
        Dict with keys ``apply_fixes``, ``fix_mathjax_escapes``,
        ``parse_frontmatter``, ``rebuild_markdown_with_frontmatter``.

    """
    content = p.read_text(encoding="utf-8")
    content = text_utils["apply_fixes"](content)
    content = text_utils["fix_mathjax_escapes"](content)

    parse_fm = text_utils["parse_frontmatter"]
    meta, body = parse_fm(content)

    if not meta:
        return content

    if "__yaml_error__" in meta:
        if config.verbose >= 2:
            # Return None to signal caller to skip; caller handles messaging.
            pass
        return None

    if not _upgrade_to_arete(meta):
        return None

    _heal_cards(meta)

    new_ids = ensure_card_ids(meta)
    if new_ids > 0 and config.verbose >= 1:
        pass  # Caller handles messaging.

    body = _strip_redundant_frontmatter(body, parse_fm)
    normalized = text_utils["rebuild_markdown_with_frontmatter"](meta, body)

    if content.startswith("\ufeff"):
        normalized = "\ufeff" + normalized
    return normalized

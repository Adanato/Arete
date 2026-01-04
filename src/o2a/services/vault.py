import hashlib
import logging
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ..consts import CURRENT_TEMPLATE_VERSION
from ..domain.types import UpdateItem
from ..infrastructure.cache import ContentCache
from ..infrastructure.fs import iter_markdown_files
from ..text import parse_frontmatter, rebuild_markdown_with_frontmatter
from ..utils import sanitize


class VaultService:
    def __init__(self, root: Path, cache: ContentCache, ignore_cache: bool = False):
        self.root = root
        self.cache = cache
        self.ignore_cache = ignore_cache
        self.logger = logging.getLogger(__name__)

    def scan_for_compatible_files(self) -> Iterable[tuple[Path, dict[str, Any]]]:
        """
        Iterates over all markdown files in the vault, checks them for validity
        (frontmatter, version), and yields valid files.
        """
        for p in iter_markdown_files(self.root):
            ok, _, reason, meta = self._quick_check_file(p)
            if ok and meta:
                cards_count = len(meta.get("cards", []))
                self.logger.debug(
                    f"[vault] Accepted {p.name} (v{meta.get('anki_template_version')}) "
                    f"cards={cards_count}"
                )
                yield p, meta
            else:
                self.logger.debug(f"[vault] Skipped {p.name}: {reason}")

    def _quick_check_file(
        self, md_file: Path
    ) -> tuple[bool, int, str | None, dict[str, Any] | None]:
        # Logic adapted from logic._quick_check_file
        try:
            text = md_file.read_text(encoding="utf-8", errors="strict")
            file_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
        except Exception as e:
            return (False, 0, f"read_error:{e}", None)

        if self.cache and not self.ignore_cache:
            cached_meta = self.cache.get_file_meta(md_file, file_hash)
            if cached_meta:
                try:
                    cards = cached_meta.get("cards", [])
                    return (True, len(cards), None, cached_meta)
                except Exception:
                    pass

        meta, _body = parse_frontmatter(text)
        if not meta or "__yaml_error__" in meta:
            return (False, 0, "no_or_bad_yaml", None)

        v = meta.get("anki_template_version") or meta.get("anki_plugin_version")
        try:
            v = int(str(v).strip().strip('"').strip("'"))
        except Exception:
            return (False, 0, "bad_template_version", None)

        if v != CURRENT_TEMPLATE_VERSION:
            return (
                False,
                0,
                f"wrong_template_version_got_{v}_expected_{CURRENT_TEMPLATE_VERSION}",
                None,
            )

        cards = meta.get("cards", [])
        if not isinstance(cards, list) or not cards:
            return (False, 0, "no_cards", None)

        deck = meta.get("deck")
        # basic check
        has_any_card_deck = any(isinstance(c, dict) and c.get("deck") for c in cards)
        if not deck and not has_any_card_deck:
            return (False, 0, "no_deck", None)

        # Save to cache
        if self.cache:
            self.cache.set_file_meta(md_file, file_hash, meta)

        return (True, len(cards), None, meta)

    def apply_updates(self, updates: list[UpdateItem]):
        """
        Writes back new NIDs/CIDs to the markdown files.
        """
        by_file: dict[Path, list[UpdateItem]] = defaultdict(list)
        for u in updates:
            if u.ok and (u.new_nid or u.new_cid):
                by_file[u.source_file].append(u)

        for md_path, ups in by_file.items():
            try:
                text = md_path.read_text(encoding="utf-8")
                meta, body = parse_frontmatter(text)
                if not meta or "__yaml_error__" in meta:
                    continue
                cards = meta.get("cards", [])
                changed = False
                for u in ups:
                    i = u.source_index - 1
                    if 0 <= i < len(cards):
                        c = cards[i]
                        if u.new_nid and sanitize(c.get("nid", "")) != u.new_nid:
                            c["nid"] = u.new_nid
                            changed = True
                        if u.new_cid and sanitize(c.get("cid", "")) != u.new_cid:
                            c["cid"] = u.new_cid
                            changed = True
                if changed:
                    meta["cards"] = cards
                    new_text = rebuild_markdown_with_frontmatter(meta, body)
                    if new_text != text:
                        md_path.write_text(new_text, encoding="utf-8")
                        self.logger.debug(f"[write] {md_path}: persisted nid/cid into frontmatter")
            except Exception as e:
                self.logger.error(f"[error] write-updates {md_path}: {e}")

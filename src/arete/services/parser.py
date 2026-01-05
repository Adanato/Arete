import hashlib
import logging
from pathlib import Path
from typing import Any

from ..domain.types import AnkiNote
from ..infrastructure.cache import ContentCache
from ..media import transform_images_in_text
from ..text import convert_math_to_tex_delimiters, make_editor_note
from ..utils import sanitize, to_list


class MarkdownParser:
    def __init__(
        self, vault_root: Path, anki_media_dir: Path, logger: logging.Logger | None = None
    ):
        self.vault_root = vault_root
        self.anki_media_dir = anki_media_dir
        self.logger = logger or logging.getLogger(__name__)

    def parse_file(
        self,
        md_path: Path,
        meta: dict[str, Any],
        cache: ContentCache,
        name_index: dict[str, list[Path]] | None = None,
    ) -> tuple[list[AnkiNote], list[int], list[dict[str, str | None]]]:
        deck_frontmatter = sanitize(meta.get("deck", "")) or None
        default_model = sanitize(meta.get("model", "Basic"))
        base_tags = [t.strip() for t in to_list(meta.get("tags", [])) if t and t.strip()]
        cards = meta.get("cards", [])

        self.logger.debug(
            f"[parser] Parsing {md_path.name}. Frontmatter deck={deck_frontmatter}, "
            f"model={default_model}, cards={len(cards)}"
        )

        notes: list[AnkiNote] = []
        skipped_indices: list[int] = []
        inventory: list[dict[str, str | None]] = []

        for idx, card in enumerate(cards, start=1):
            try:
                model = sanitize(card.get("model", default_model))
                mlow = model.lower()
                fields = {}

                # Field validation logic
                if mlow == "basic":
                    fields = {
                        "Front": sanitize(card.get("Front", "")),
                        "Back": sanitize(card.get("Back", "")),
                    }
                    if not fields["Front"] or not fields["Back"]:
                        self.logger.debug(
                            f"[skip] {md_path} card#{idx}: Basic requires Front & Back"
                        )
                        skipped_indices.append(idx)
                        continue
                elif mlow == "cloze":
                    fields = {
                        "Text": sanitize(card.get("Text", "")),
                        "Back Extra": sanitize(card.get("Back Extra", ""))
                        or sanitize(card.get("Extra", "")),
                    }
                    if not fields["Text"]:
                        self.logger.debug(f"[skip] {md_path} card#{idx}: Cloze requires Text")
                        skipped_indices.append(idx)
                        continue
                else:
                    # Allow 'nid' to pass through for custom models so it can be stored in Anki
                    _exclude = {"cid", "model", "deck", "tags", "markdown"}
                    fields = {k: sanitize(v) for k, v in card.items() if k not in _exclude}

                    if not fields:
                        self.logger.debug(
                            f"[skip] {md_path} card#{idx}: custom model '{model}' has no fields"
                        )
                        skipped_indices.append(idx)
                        continue

                # 1) Convert math + images
                for fk, fv in list(fields.items()):
                    if isinstance(fv, str) and fv:
                        txt = convert_math_to_tex_delimiters(fv)
                        fields[fk] = transform_images_in_text(
                            txt,
                            md_path,
                            self.vault_root,
                            self.anki_media_dir,
                            self.logger,
                            name_index=name_index,
                        )

                # 2) IDs
                nid = sanitize(card.get("nid", "")).strip() or None
                cid = sanitize(card.get("cid", "")).strip() or None

                # 3) Deck
                deck_this = (
                    sanitize(card.get("deck", deck_frontmatter))
                    if deck_frontmatter
                    else sanitize(card.get("deck"))
                )
                if not deck_this:
                    self.logger.debug(f"[skip] {md_path} card#{idx}: no deck set")
                    skipped_indices.append(idx)
                    continue

                # NEW: Track as valid inventory for Prune Mode
                # We must record the deck even if NID is missing (to protect the deck from deletion)
                inventory.append({"nid": nid, "deck": deck_this})

                # 4) Calculate hash check
                # We use make_editor_note to produce the canonical content for hashing
                content = make_editor_note(
                    model, deck_this, base_tags, fields, nid=nid, cid=cid, markdown=True
                )
                content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()

                cached_hash = cache.get_hash(md_path, idx)
                if cached_hash == content_hash:
                    self.logger.debug(f"[cache-hit] {md_path} card#{idx}: skipping")
                    continue

                notes.append(
                    AnkiNote(
                        model=model,
                        deck=deck_this,
                        fields=fields,
                        tags=base_tags,
                        start_line=0,
                        end_line=0,
                        nid=nid,
                        cid=cid,
                        content_hash=content_hash,
                        source_file=md_path,
                        source_index=idx,
                    )
                )
            except Exception as e:
                self.logger.error(f"[error] {md_path} card#{idx}: {e}")
                skipped_indices.append(idx)

        self.logger.debug(
            f"[parser] Finished {md_path.name}. notes={len(notes)}, "
            f"skipped={len(skipped_indices)}, inventory={len(inventory)}"
        )
        return notes, skipped_indices, inventory

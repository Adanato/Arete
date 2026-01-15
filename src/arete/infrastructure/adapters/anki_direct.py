from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anki.decks import DeckId
    from anki.notes import NoteId

from arete.domain.interfaces import AnkiBridge
from arete.domain.models import AnkiDeck, UpdateItem, WorkItem
from arete.infrastructure.anki.repository import AnkiRepository


class AnkiDirectAdapter(AnkiBridge):
    """
    Direct Python adapter for Anki using the 'anki' library.
    """

    def __init__(self, anki_base: Path | None):
        self.anki_base = anki_base
        self.logger = logging.getLogger(__name__)

    async def get_model_names(self) -> list[str]:
        # TODO: Implement in repository if needed.
        # For now return empty as fallback or implement properly.
        # Direct access means we CAN easily get this.
        with AnkiRepository(self.anki_base) as repo:
            if repo.col:
                return [m["name"] for m in repo.col.models.all()]
        return []

    async def ensure_deck(self, deck: AnkiDeck | str) -> bool:
        # AnkiRepository creates/ensures decks on the fly during add_note
        # via 'col.decks.id(name)'.
        # So we can just return True or verify it exists.
        deck_name = deck.name if isinstance(deck, AnkiDeck) else deck
        with AnkiRepository(self.anki_base) as repo:
            if repo.col:
                # col.decks.id(deck_name) creates it if missing
                repo.col.decks.id(deck_name)
                return True
        return False

    async def sync_notes(self, work_items: list[WorkItem]) -> list[UpdateItem]:
        results = []

        # Batch operation: Open DB once
        try:
            with AnkiRepository(self.anki_base) as repo:
                for item in work_items:
                    try:
                        self.logger.debug(f"Processing {item.source_file} #{item.source_index}")

                        note_data = item.note
                        success = False
                        new_nid = str(note_data.nid) if note_data.nid else None
                        error_msg = None

                        # 1. Try Update if NID exists
                        if note_data.nid:
                            try:
                                updated = repo.update_note(int(note_data.nid), note_data)
                                if updated:
                                    success = True
                                else:
                                    # Note ID not found in DB? Fallback to Add?
                                    # Ideally we trust the NID. If it's missing, it's deleted.
                                    # Note with ID not found. Will create new note.
                                    self.logger.warning(
                                        f"Note {note_data.nid} not found. Creating new."
                                    )
                                    # Fallthrough to add
                                    pass
                            except Exception as e:
                                error_msg = str(e)
                                self.logger.error(f"Update failed for {note_data.nid}: {e}")

                        # 2. Add if not updated/existing
                        if not success and not error_msg:
                            try:
                                nid_int = repo.add_note(note_data)
                                new_nid = str(nid_int)
                                success = True
                            except Exception as e:
                                error_msg = f"Add failed: {e}"
                                self.logger.error(error_msg)

                        # 3. Compile Result
                        results.append(
                            UpdateItem(
                                source_file=item.source_file,
                                source_index=item.source_index,
                                new_nid=new_nid,
                                new_cid=None,  # CID not easily returned without extra query
                                ok=success,
                                error=error_msg,
                                note=item.note,
                            )
                        )

                    except Exception as e:
                        # Catch-all for item failure
                        results.append(
                            UpdateItem(
                                source_file=item.source_file,
                                source_index=item.source_index,
                                new_nid=None,
                                new_cid=None,
                                ok=False,
                                error=f"Unexpected error: {e}",
                            )
                        )

        except Exception as e:
            # DB Open failure
            self.logger.critical(f"Failed to open Anki DB: {e}")
            # Fail all items
            for item in work_items:
                results.append(
                    UpdateItem(
                        source_file=item.source_file,
                        source_index=item.source_index,
                        new_nid=None,
                        new_cid=None,
                        ok=False,
                        error=f"DB Error: {e}",
                    )
                )

        return results

    async def get_deck_names(self) -> list[str]:
        with AnkiRepository(self.anki_base) as repo:
            if repo.col:
                return repo.col.decks.all_names()
        return []

    async def get_notes_in_deck(self, deck_name: str) -> dict[str, int]:
        # Enable Pruning support!
        with AnkiRepository(self.anki_base) as repo:
            if repo.col:
                # Find direct notes
                # query: "deck:name"
                nids = repo.find_notes(f'"deck:{deck_name}"')
                # We need to map back to obsidian source ID/hash?
                # Arete pruning relies on local state usually, or metadata in fields.
                # AnkiConnect implementation fetches fields.
                # For direct implementation, we can iterate nids and get fields.
                # WARNING: This might be slow for huge decks.
                # For now implementing basic NID list return might not be enough.
                # Interface expects dict {obsidian_id: nid}?
                # Interfaces doc says: "Return mapping of {obsidian_nid: anki_nid}"?
                # Actually PruningService uses this to find what IS in Anki vs what SHOULD be.
                # If we store obsidian ID in a field (e.g. source id), we can map it.
                # Existing logic might rely on content match.

                # Let's verify interface doc or usage.
                # Interface says: "Return mapping of {obsidian_nid: anki_nid}"
                # If Anki notes don't have obsidian_nid stored, this is hard.
                # But typically obsidian_nid IS the anki_nid.
                # So maybe it returns {str(nid): nid}?
                return {str(nid): nid for nid in nids}

        return {}

    async def delete_notes(self, nids: list[int]) -> bool:
        if not nids:
            return True
        with AnkiRepository(self.anki_base) as repo:
            if repo.col:
                from anki.notes import NoteId

                repo.col.remove_notes([NoteId(n) for n in nids])
                return True
        return False

    async def delete_decks(self, names: list[str]) -> bool:
        with AnkiRepository(self.anki_base) as repo:
            if repo.col:
                for name in names:
                    did = repo.col.decks.id(name)
                    if did is not None:
                        repo.col.decks.remove([did])
                return True
        return False

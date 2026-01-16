import asyncio
import json
import logging
import os
import platform
import shutil
from typing import Any

import httpx

from arete.domain.interfaces import AnkiBridge
from arete.domain.models import AnkiCardStats, AnkiDeck, UpdateItem, WorkItem


class AnkiConnectAdapter(AnkiBridge):
    """
    Adapter for communicating with Anki via the AnkiConnect add-on (HTTP API).
    """

    def __init__(self, url: str = "http://127.0.0.1:8765"):
        self.logger = logging.getLogger(__name__)
        self._known_decks = set()
        self._model_fields_cache = {}
        self.use_windows_curl = False
        self._client: httpx.AsyncClient | None = None

        # 1. Environment Variable Override (Highest Priority)
        env_host = os.environ.get("ANKI_CONNECT_HOST")
        if env_host:
            # If user provides a host (e.g. 192.168.1.5), we reconstruct the URL
            # Assumes port 8765 if not specified, or user can provide full authority?
            # Let's assume input is just the host IP/name
            url = f"http://{env_host}:8765"
            self.logger.info(f"Using ANKI_CONNECT_HOST override: {url}")
            self.url = url
            return

        # 2. WSL Logic
        if "microsoft" in platform.uname().release.lower():
            # Strategy A: curl.exe bridge (Preferred for 127.0.0.1)
            curl_path = shutil.which("curl.exe")
            if curl_path:
                self.use_windows_curl = True
                if "127.0.0.1" in url or "localhost" in url:
                    url = url.replace("localhost", "127.0.0.1")
                self.logger.info(
                    f"WSL detected: Using curl.exe bridge (found at {curl_path}) to talk to {url}"
                )
                self.url = url
                return
            else:
                self.logger.debug("WSL detected but 'curl.exe' not found in PATH.")

            # Strategy B: /etc/resolv.conf (Fallback)
            if "localhost" in url or "127.0.0.1" in url:
                try:
                    with open("/etc/resolv.conf") as f:
                        for line in f:
                            if line.startswith("nameserver"):
                                host_ip = line.split()[1].strip()
                                url = url.replace("localhost", host_ip).replace(
                                    "127.0.0.1", host_ip
                                )
                                self.logger.info(
                                    f"WSL detected: Auto-corrected URL using resolv.conf to http://{host_ip}:8765"
                                )
                                break
                except Exception as e:
                    self.logger.warning(f"WSL detected but failed to find host IP: {e}")

        self.url = url
        self.logger.debug(
            f"AnkiConnectAdapter initialized with url={self.url} "
            f"(curl_bridge={self.use_windows_curl})"
        )

    @property
    def is_sequential(self) -> bool:
        return False

    async def is_responsive(self) -> bool:
        """Check if AnkiConnect is reachable and has the expected API version."""
        try:
            # We can check version
            # Use a short timeout for responsiveness check
            payload = {"action": "version", "version": 6}
            async with httpx.AsyncClient() as client:
                resp = await client.post(self.url, json=payload, timeout=2.0)
                if resp.status_code == 200:
                    data = resp.json()
                    return int(data.get("result", 0)) >= 6
            return False
        except Exception:
            return False

    async def get_model_names(self) -> list[str]:
        return await self._invoke("modelNames")

    async def ensure_deck(self, deck: AnkiDeck | str) -> bool:
        name = deck.name if isinstance(deck, AnkiDeck) else deck
        if name in self._known_decks:
            return True
        try:
            await self._invoke("createDeck", deck=name)
            self._known_decks.add(name)
            return True
        except Exception as e:
            self.logger.error(f"Failed to ensure deck '{name}': {e}")
            return False

    async def ensure_model_has_source_field(self, model_name: str) -> bool:
        """
        Ensure the note model has the _obsidian_source field.
        This enables backwards compatibility for existing cards.
        """
        cache_key = f"_source_field_{model_name}"
        if hasattr(self, cache_key):
            return True

        try:
            # Get current model fields
            fields = await self._invoke("modelFieldNames", modelName=model_name)
            if "_obsidian_source" not in fields:
                # Add the field to the model
                await self._invoke(
                    "modelFieldAdd",
                    modelName=model_name,
                    fieldName="_obsidian_source",
                )
                self.logger.info(f"Added '_obsidian_source' field to model '{model_name}'")

            setattr(self, cache_key, True)
            return True
        except Exception as e:
            self.logger.warning(f"Could not add _obsidian_source field to '{model_name}': {e}")
            return False

    async def sync_notes(self, work_items: list[WorkItem]) -> list[UpdateItem]:
        # Batch preparation: Ensure decks and models exist once per batch
        unique_decks = {item.note.deck for item in work_items}
        unique_models = {item.note.model for item in work_items}

        for deck_name in unique_decks:
            if not await self.ensure_deck(deck_name):
                # We could fail the whole batch, or just mark them as failed later.
                # For now, failures in ensure_deck will be caught by individual item try-blocks
                # But it's better to log here.
                self.logger.warning(f"Failed to ensure deck '{deck_name}' for batch")

        for model_name in unique_models:
            try:
                await self.ensure_model_has_source_field(model_name)
            except Exception as e:
                self.logger.warning(f"Failed to ensure source field for '{model_name}': {e}")

        tasks = [self._sync_single_note(item) for item in work_items]
        return list(await asyncio.gather(*tasks))

    async def _sync_single_note(self, item: WorkItem) -> UpdateItem:
        note = item.note
        try:
            # Fields are already HTML from parser
            # Skip _obsidian_source from being treated as content field if model is strict
            html_fields = {}
            for k, v in note.fields.items():
                # _obsidian_source is passed through as-is (it's plain text anyway)
                html_fields[k] = v

            target_nid = None
            info = None
            if note.nid:
                # check existence
                info = await self._invoke("notesInfo", notes=[int(note.nid)])
                if info and info[0].get("noteId"):
                    target_nid = int(note.nid)

            if target_nid:
                # UPDATE
                await self._invoke(
                    "updateNoteFields", note={"id": target_nid, "fields": html_fields}
                )

                # Update Tags
                if info and "tags" in info[0]:
                    current_tags = set(info[0]["tags"])
                    new_tags = set(note.tags)

                    to_add = list(new_tags - current_tags)
                    to_remove = list(current_tags - new_tags)

                    if to_add:
                        await self._invoke("addTags", notes=[target_nid], tags=" ".join(to_add))
                    if to_remove:
                        await self._invoke(
                            "removeTags", notes=[target_nid], tags=" ".join(to_remove)
                        )

                # Move cards if needed
                if info and "cards" in info[0]:
                    cids = info[0]["cards"]
                    await self._invoke("changeDeck", cards=cids, deck=note.deck)
                else:
                    self.logger.warning(
                        f"[anki] Cannot move cards for nid={target_nid}. Info missing cards: {info}"
                    )

                self.logger.debug(
                    f"[update] {item.source_file} #{item.source_index} -> nid={target_nid}"
                )
                return UpdateItem(
                    source_file=item.source_file,
                    source_index=item.source_index,
                    new_nid=str(target_nid),
                    new_cid=None,
                    ok=True,
                    note=note,
                )

            else:
                # ADD / HEAL
                # Proactive Healing: Check if content already exists to avoid creation
                import re

                first_field_val = list(html_fields.values())[0]
                # Clean for search query
                cleaned_val = re.sub(r"<[^>]+>", "", first_field_val)
                cleaned_val = cleaned_val.translate(
                    str.maketrans({"\r": " ", "\n": " ", "\t": " ", "\v": " ", "\f": " "})
                ).strip()
                cleaned_val = cleaned_val.replace("\\", "\\\\").replace('"', '\\"')
                if len(cleaned_val) > 100:
                    cleaned_val = cleaned_val[:100]

                existing_nid = None
                if cleaned_val:
                    query = f'"deck:{note.deck}" "{cleaned_val}"'
                    try:
                        candidates = await self._invoke("findNotes", query=query)
                        if candidates and len(candidates) >= 1:
                            existing_nid = candidates[0]
                            self.logger.info(
                                " -> Healed! matched existing note ID via proactive search: "
                                f"{existing_nid}"
                            )
                    except Exception as e_search:
                        self.logger.warning(f"Healing search failed: {e_search}")

                if existing_nid:
                    new_id = existing_nid
                    # We might want to update fields even if we found it?
                    # Ideally yes, let's treat it as an update now that we found it.
                    await self._invoke(
                        "updateNoteFields", note={"id": new_id, "fields": html_fields}
                    )
                else:
                    # CREATE
                    params = {
                        "note": {
                            "deckName": note.deck,
                            "modelName": note.model,
                            "fields": html_fields,
                            "tags": note.tags,
                            "options": {
                                "allowDuplicate": False,
                                "duplicateScope": "deck",
                            },
                        }
                    }
                    new_id = await self._invoke("addNote", **params)
                    if not new_id:
                        raise Exception("addNote returned null ID")

                # FETCH CID Logic
                new_cid_val = None
                try:
                    info_new = await self._invoke("notesInfo", notes=[new_id])
                    if info_new and info_new[0].get("cards"):
                        new_cid_val = str(info_new[0]["cards"][0])
                except Exception as e_cid:
                    self.logger.warning(f"Failed to fetch CID for nid={new_id}: {e_cid}")

                # Post-creation: Populate 'nid' field if it exists in the model
                try:
                    if note.model not in self._model_fields_cache:
                        self._model_fields_cache[note.model] = await self._invoke(
                            "modelFieldNames", modelName=note.model
                        )
                    model_fields = self._model_fields_cache[note.model]
                    if "nid" in model_fields:
                        await self._invoke(
                            "updateNoteFields",
                            note={"id": new_id, "fields": {"nid": str(new_id)}},
                        )
                except Exception as e_field:
                    self.logger.warning(f"Failed to populate 'nid' field: {e_field}")

                self.logger.info(
                    f"[create] {item.source_file} #{item.source_index} -> "
                    f"nid={new_id} cid={new_cid_val}"
                )
                return UpdateItem(
                    source_file=item.source_file,
                    source_index=item.source_index,
                    new_nid=str(new_id),
                    new_cid=new_cid_val,
                    ok=True,
                    note=note,
                )

        except Exception as e:
            msg = f"ERR file={item.source_file} card={item.source_index} error={e}"
            self.logger.error(msg)
            return UpdateItem(
                source_file=item.source_file,
                source_index=item.source_index,
                new_nid=None,
                new_cid=None,
                ok=False,
                error=str(e),
                note=note,
            )

    async def _invoke(self, action: str, **params) -> Any:
        payload = {"action": action, "version": 6, "params": params}
        try:
            if self.use_windows_curl:
                # Use curl.exe indirectly via async subprocess
                import asyncio

                cmd = ["curl.exe", "-s", "-X", "POST", self.url, "-d", "@-"]
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=json.dumps(payload).encode("utf-8")), timeout=30
                )
                if proc.returncode != 0:
                    raise Exception(f"curl.exe failed: {stderr.decode('utf-8')}")

                data = json.loads(stdout.decode("utf-8"))
            else:
                # Standard httpx (Async) - Reuse client
                if self._client is None:
                    self._client = httpx.AsyncClient(timeout=30.0)

                resp = await self._client.post(self.url, json=payload)
                resp.raise_for_status()
                data = resp.json()

            if len(data) != 2:
                raise ValueError("response has an unexpected number of fields")
            if "error" not in data:
                raise ValueError("response is missing required error field")
            if "result" not in data:
                raise ValueError("response is missing required result field")
            if data["error"] is not None:
                raise Exception(data["error"])
            return data["result"]
        except Exception as e:
            self.logger.error(f"AnkiConnect call failed: {e}")
            raise

    async def get_deck_names(self) -> list[str]:
        return await self._invoke("deckNames")

    async def get_notes_in_deck(self, deck_name: str) -> dict[str, int]:
        # 1. Find notes in deck
        query = f'"deck:{deck_name}"'
        nids = await self._invoke("findNotes", query=query)
        if not nids:
            return {}

        # 2. Get note info to extract 'nid' field
        info = await self._invoke("notesInfo", notes=nids)
        result = {}
        for note in info:
            note_id = note.get("noteId")
            fields = note.get("fields", {})
            nid_val = None
            if "nid" in fields:
                nid_val = fields["nid"]["value"]
                # Strip HTML
                if nid_val.startswith("<p>") and nid_val.endswith("</p>"):
                    nid_val = nid_val[3:-4].strip()

            if nid_val:
                result[nid_val] = note_id
            else:
                self.logger.debug(
                    f"[anki] Note {note_id} has no valid NID. raw_field={fields.get('nid')}"
                )

        self.logger.debug(
            f"[anki] get_notes_in_deck found {len(result)} notes with NIDs in {deck_name}"
        )
        return result

    async def delete_notes(self, nids: list[int]) -> bool:
        self.logger.info(f"Deleting notes: {nids}")
        await self._invoke("deleteNotes", notes=nids)
        return True

    async def delete_decks(self, names: list[str]) -> bool:
        await self._invoke("deleteDecks", decks=names, cardsToo=True)
        return True

    async def get_learning_insights(self, lapse_threshold: int = 3) -> Any:
        from arete.application.stats_service import StatsService

        service = StatsService(self)
        service = StatsService(self)
        return await service.get_learning_insights(lapse_threshold=lapse_threshold)

    async def get_card_stats(self, nids: list[int]) -> list[AnkiCardStats]:
        """
        Fetch stats via AnkiConnect.
        """
        all_stats = []
        if not nids:
            return []

        CHUNK_SIZE = 500
        for i in range(0, len(nids), CHUNK_SIZE):
            chunk = nids[i : i + CHUNK_SIZE]

            try:
                # 1. Find Cards
                query = " OR ".join([f"nid:{n}" for n in chunk])
                card_ids = await self._invoke("findCards", query=query)
                if not card_ids:
                    continue

                # 2. Get Info
                infos = await self._invoke("cardsInfo", cards=card_ids)

                # 3. Get FSRS (Custom Action check)
                fsrs_map = {}
                try:
                    fsrs_results = await self._invoke("getFSRSStats", cards=card_ids)
                    if fsrs_results and isinstance(fsrs_results, list):
                        for item in fsrs_results:
                            if (
                                "cardId" in item
                                and "difficulty" in item
                                and item["difficulty"] is not None
                            ):
                                fsrs_map[item["cardId"]] = item["difficulty"] / 10.0
                except Exception:
                    # Ignore if FSRS action missing
                    pass

                for info in infos:
                    cid = info.get("cardId")
                    difficulty = fsrs_map.get(cid)
                    if difficulty is None:
                        difficulty = info.get("difficulty")  # Standard field fallback

                    # Front? info usually has fields, not rendered front.
                    # We could try to extract from fields if needed, but for now leave None
                    # or grab first field.
                    front = None
                    fields = info.get("fields", {})
                    if fields:
                        # Grab first field value
                        first_key = list(fields.keys())[0]
                        front = fields[first_key].get("value")

                    all_stats.append(
                        AnkiCardStats(
                            card_id=cid,
                            note_id=info.get("note"),
                            lapses=info.get("lapses", 0),
                            ease=info.get("factor", 0),
                            difficulty=difficulty,
                            deck_name=info.get("deckName", "Unknown"),
                            interval=info.get("interval", 0),
                            due=info.get("due", 0),
                            reps=info.get("reps", 0),
                            average_time=0,
                            front=front,
                        )
                    )

            except Exception as e:
                self.logger.error(f"Failed to fetch card stats chunk: {e}")

        return all_stats

    async def suspend_cards(self, cids: list[int]) -> bool:
        if not cids:
            return True  # Nothing to do
        res = await self._invoke("suspend", cards=cids)
        return bool(res)

    async def unsuspend_cards(self, cids: list[int]) -> bool:
        if not cids:
            return True
        res = await self._invoke("unsuspend", cards=cids)
        return bool(res)

    async def get_model_styling(self, model_name: str) -> str:
        try:
            res = await self._invoke("modelStyling", modelName=model_name)
            if isinstance(res, dict):
                return res.get("css", "")
            return str(res)
        except Exception:
            return ""

    async def get_model_templates(self, model_name: str) -> dict[str, dict[str, str]]:
        try:
            res = await self._invoke("modelTemplates", modelName=model_name)
            # AnkiConnect returns { "Card 1": { "Front": "...", "Back": "..." } }
            return res
        except Exception:
            return {}

    async def gui_browse(self, query: str) -> bool:
        """Open the Anki browser via AnkiConnect's guiBrowse action."""
        try:
            await self._invoke("guiBrowse", query=query)
            return True
        except Exception as e:
            self.logger.error(f"Failed to open Anki browser: {e}")
            return False

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

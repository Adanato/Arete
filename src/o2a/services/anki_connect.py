import json
import logging
import os
import platform
import re
import shutil
from typing import Any

import httpx
import markdown

from ..domain.interfaces import AnkiBridge
from ..domain.types import AnkiDeck, UpdateItem, WorkItem


class AnkiConnectAdapter(AnkiBridge):
    """
    Adapter for communicating with Anki via the AnkiConnect add-on (HTTP API).
    """

    def __init__(self, url: str = "http://localhost:8765"):
        self.logger = logging.getLogger(__name__)
        self._known_decks = set()
        self.use_windows_curl = False

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
                if "localhost" in url:
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
        self.logger.info(
            f"AnkiConnectAdapter initialized with url={self.url} "
            f"(curl_bridge={self.use_windows_curl})"
        )

    async def is_responsive(self) -> bool:
        """Check if AnkiConnect is reachable and has the expected API version."""
        try:
            # We can check version
            res = await self._invoke("version")
            return int(res) >= 6
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

    async def sync_notes(self, work_items: list[WorkItem]) -> list[UpdateItem]:
        results = []
        for item in work_items:
            try:
                note = item.note

                # Convert fields to HTML while preserving MathJax
                html_fields = {k: self._to_html(v) for k, v in note.fields.items()}

                # Ensure deck exists
                await self.ensure_deck(note.deck)

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
                    # 1. Get current tags
                    # 2. Add/Remove difference OR just replace?
                    # AnkiConnect 'updateNoteTags' (if exists) or 'removeTags' + 'addTags'
                    # More robust: 'replaceTags' action? No.
                    # "notesInfo" returns "tags": ["tag1", ...]

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
                    # ... [existing move logic] ...
                    if info and "cards" in info[0]:
                        cids = info[0]["cards"]
                        # self.logger.debug(f"[anki] Moving cards {cids} to deck '{note.deck}'")
                        await self._invoke("changeDeck", cards=cids, deck=note.deck)
                        # self.logger.debug(f"[anki] changeDeck result: {res}")
                    else:
                        self.logger.warning(
                            f"[anki] Cannot move cards for nid={target_nid}. "
                            f"Info missing cards: {info}"
                        )

                    results.append(
                        UpdateItem(
                            source_file=item.source_file,
                            source_index=item.source_index,
                            new_nid=str(target_nid),
                            new_cid=None,
                            ok=True,
                            note=note,
                        )
                    )
                    self.logger.debug(
                        f"[update] {item.source_file} #{item.source_index} -> nid={target_nid}"
                    )

                else:
                    # ADD
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
                    try:
                        new_id = await self._invoke("addNote", **params)
                        if not new_id:
                            raise Exception("addNote returned null ID")
                    except Exception as e:
                        # HEALING LOGIC: If duplicate, try to find the existing card
                        if "duplicate" in str(e).lower():
                            self.logger.warning(
                                f"Duplicate detected for {item.source_file.name}. "
                                "Attempting to identify existing note..."
                            )

                            first_field_val = list(html_fields.values())[0]
                            cleaned_val = first_field_val.translate(
                                str.maketrans(
                                    {"\r": " ", "\n": " ", "\t": " ", "\v": " ", "\f": " "}
                                )
                            )
                            cleaned_val = cleaned_val.replace("\\", "\\\\").replace('"', '\\"')
                            if len(cleaned_val) > 100:
                                cleaned_val = cleaned_val[:100]

                            query = f'"deck:{note.deck}" "{cleaned_val}"'
                            try:
                                candidates = await self._invoke("findNotes", query=query)
                                if candidates and len(candidates) >= 1:
                                    new_id = candidates[0]
                                    self.logger.info(
                                        f" -> Healed! matched existing note ID: {new_id}"
                                    )
                                else:
                                    raise e
                            except Exception:
                                raise e from None

                        else:
                            raise e

                    # FETCH CID Logic
                    new_cid_val = None
                    try:
                        info_new = await self._invoke("notesInfo", notes=[new_id])
                        if info_new and info_new[0].get("cards"):
                            new_cid_val = str(info_new[0]["cards"][0])
                    except Exception as e_cid:
                        self.logger.warning(f"Failed to fetch CID for nid={new_id}: {e_cid}")

                    results.append(
                        UpdateItem(
                            source_file=item.source_file,
                            source_index=item.source_index,
                            new_nid=str(new_id),
                            new_cid=new_cid_val,
                            ok=True,
                            note=note,
                        )
                    )
                    self.logger.info(
                        f"[create] {item.source_file} #{item.source_index} -> "
                        f"nid={new_id} cid={new_cid_val}"
                    )

            except Exception as e:
                msg = f"ERR file={item.source_file} card={item.source_index} error={e}"
                self.logger.error(msg)
                results.append(
                    UpdateItem(
                        source_file=item.source_file,
                        source_index=item.source_index,
                        new_nid=None,
                        new_cid=None,
                        ok=False,
                        error=str(e),
                        note=note,
                    )
                )
        return results

    def _to_html(self, text: str) -> str:
        r"""
        Convert Markdown to HTML, but protect MathJax blocks delimiters
        \( ... \) and \[ ... \] from being escaped/mangled.
        """
        # Store protected blocks
        protected = {}

        def protect(m):
            key = f"MATHJAXBLOCK{len(protected)}"
            protected[key] = m.group(0)
            return key

        # Regex for \( ... \) and \[ ... \]
        # We need to be careful with backslashes in regex
        # Pattern: \\\[.*?\\\]  and \\\((.*?)\\\)
        # flags=re.DOTALL to match newlines in blocks

        # Protect block math \[ ... \]
        text = re.sub(r"\\\[.*?\\\]", protect, text, flags=re.DOTALL)

        # Protect inline math \( ... \)
        text = re.sub(r"\\\(.*?\\\)", protect, text, flags=re.DOTALL)

        # Convert to HTML
        html = markdown.markdown(text, extensions=["tables", "fenced_code"])

        # Restore protected blocks
        for key, val in protected.items():
            html = html.replace(key, val)

        return html

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
                # Standard httpx (Async)
                async with httpx.AsyncClient() as client:
                    resp = await client.post(self.url, json=payload, timeout=30.0)
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
        try:
            # Ensure IDs are integers (AnkiConnect Strictness)
            safe_nids = [int(n) for n in nids]
            await self._invoke("deleteNotes", notes=safe_nids)
            return True
        except Exception as e:
            self.logger.error(f"deleteNotes FAILED: {e}")
            return False

    async def delete_decks(self, names: list[str]) -> bool:
        try:
            await self._invoke("deleteDecks", decks=names, cardsToo=True)
            return True
        except Exception:
            return False

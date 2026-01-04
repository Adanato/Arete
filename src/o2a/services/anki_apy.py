import asyncio
import logging
import os
import tempfile
from pathlib import Path

from ..consts import RE_CID, RE_NID
from ..domain.interfaces import AnkiBridge
from ..domain.types import AnkiDeck, UpdateItem, WorkItem
from ..text import make_editor_note


class AnkiApyAdapter(AnkiBridge):
    def __init__(
        self, apy_bin: str, anki_base: Path | None, move_deck: bool = True, dry_run: bool = False
    ):
        self.apy_bin = apy_bin
        self.anki_base = anki_base
        self.move_deck = move_deck
        self.dry_run = dry_run
        self.logger = logging.getLogger(__name__)

    async def get_model_names(self) -> list[str]:
        return []

    async def ensure_deck(self, deck: AnkiDeck | str) -> bool:
        # apy creates decks on fly during note creation if needed,
        # but we can explicitly create it too if we want.
        # However, apy's CLI doesn't strictly have a 'create-deck' command exposed easily
        # without adding a note, but 'add_notes' handles it.
        # We'll just return True for now or check if it exists?
        # Apy check:
        # For this adapter, we might just assume it's fine or really implement it.
        # Let's keep it simple:
        # name = deck.name if isinstance(deck, AnkiDeck) else deck
        return True

    async def sync_notes(self, work_items: list[WorkItem]) -> list[UpdateItem]:
        results = []
        for item in work_items:
            content = make_editor_note(
                model=item.note.model,
                deck=item.note.deck,
                tags=item.note.tags,
                fields=item.note.fields,
                nid=item.note.nid,
                cid=item.note.cid,
                markdown=True,
            )

            tmp_path = self._write_temp(content, item.note.model, f"c{item.source_index}")
            rc, out, err = await self._run_apy(tmp_path)

            if rc == 0:
                new_nid, new_cid = self._parse_ids(out)
                results.append(
                    UpdateItem(
                        source_file=item.source_file,
                        source_index=item.source_index,
                        new_nid=new_nid,
                        new_cid=new_cid,
                        ok=True,
                        note=item.note,
                    )
                )
                self.logger.debug(f"[success] {item.source_file} #{item.source_index}")
            else:
                msg = (
                    f"ERR file={item.source_file} card={item.source_index} "
                    f"rc={rc} stderr={err.strip()}"
                )
                results.append(
                    UpdateItem(
                        source_file=item.source_file,
                        source_index=item.source_index,
                        new_nid=None,
                        new_cid=None,
                        ok=False,
                        error=msg,
                    )
                )
                self.logger.error(msg)

            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

        return results

    def _write_temp(self, content: str, model: str, base_hint: str = "") -> Path:
        hint = f"_{model.replace(' ', '_')}"
        if base_hint:
            hint += f"_{base_hint}"
        fd, path = tempfile.mkstemp(prefix=f"apy{hint}_", suffix=".md")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        return Path(path)

    async def _run_apy(self, path: Path) -> tuple[int, str, str]:
        cmd = [self.apy_bin]
        if self.anki_base:
            cmd.extend(["--base-path", str(self.anki_base)])

        cmd.extend(["update-from-file", "--update-file"])

        if self.move_deck:
            cmd.append("--move-deck")
        if self.dry_run:
            cmd.append("--dry-run")
        cmd.append(str(path))

        self.logger.debug(f"[apy] {' '.join(cmd)}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

            out_str = stdout.decode("utf-8")
            err_str = stderr.decode("utf-8")

            if proc.returncode == 0:
                self.logger.debug(f"[apy] Success. Output: {out_str[:200]}...")
            else:
                self.logger.debug(f"[apy] Failed (rc={proc.returncode}). Stderr: {err_str}")

            return proc.returncode or 0, out_str, err_str
        except TimeoutError:
            return 124, "", "subprocess timeout"
        except Exception as e:
            return 1, "", str(e)

    def _parse_ids(self, stdout: str) -> tuple[str | None, str | None]:
        nid = RE_NID.search(stdout)
        cid = RE_CID.search(stdout)
        return (nid.group(1) if nid else None, cid.group(1) if cid else None)

    async def get_deck_names(self) -> list[str]:
        return []

    async def get_notes_in_deck(self, deck_name: str) -> dict[str, int]:
        # If prune is attempted with apy, it calls this method.
        # We should raise an error to indicate it's not supported.
        raise ValueError(
            "[apy] Pruning is not supported for the 'auto'/'apy' backend. "
            "Please use AnkiConnect for full functionality."
        )

    async def delete_notes(self, nids: list[int]) -> bool:
        raise ValueError("[apy] delete_notes is not supported for this backend.")

    async def delete_decks(self, names: list[str]) -> bool:
        raise ValueError("[apy] delete_decks is not supported for this backend.")

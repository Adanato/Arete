import asyncio
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from tqdm import tqdm  # type: ignore
except ImportError:
    pass

from ..domain.interfaces import AnkiBridge
from ..domain.types import AnkiDeck, UpdateItem, WorkItem
from ..infrastructure.cache import ContentCache
from ..logging_utils import RunRecorder
from ..media import build_filename_index
from ..services.parser import MarkdownParser
from ..services.vault import VaultService
from .config import AppConfig


@dataclass
class RunStats:
    total_generated: int
    total_imported: int
    total_errors: int
    errors: list[UpdateItem]


async def run_pipeline(
    config: AppConfig,
    logger: logging.Logger,
    run_id: str,
    vault_service: VaultService,
    parser: MarkdownParser,
    anki_bridge: AnkiBridge,
    cache: ContentCache,
) -> RunStats:
    # Use tqdm if interactive and imported
    use_tqdm = "tqdm" in sys.modules

    recorder = RunRecorder()

    # -------- Stage 1: filter --------
    logger.info("[pipeline] Scanning vault...")
    compatible: list[tuple[Path, dict[str, Any]]] = list(vault_service.scan_for_compatible_files())

    logger.info(f"[filter] compatible files: {len(compatible)}")
    logger.debug("Compatible files:")
    for c in compatible:
        logger.debug(f"  - {c[0]}")
    if not compatible:
        logger.info("No compatible markdown files found.")
        return RunStats(0, 0, 0, [])

    # -------- Stage 2: build media index --------
    assert config.vault_root is not None  # Guaranteed by resolve_config
    name_index = build_filename_index(config.vault_root, logger)

    # -------- Stage 3: Producers + Consumer --------
    work_q: asyncio.Queue[WorkItem] = asyncio.Queue(maxsize=max(1, config.queue_size))
    updates: list[UpdateItem] = []
    updates_lock = asyncio.Lock()

    # Concurrency control:
    # AnkiConnect can handle multiple requests, but apy (SQLite/CLI) should be sequential.
    from ..services.anki_apy import AnkiApyAdapter

    max_sync_concurrency = 1 if isinstance(anki_bridge, AnkiApyAdapter) else max(1, config.workers)
    sync_semaphore = asyncio.Semaphore(max_sync_concurrency)

    async def producer_file(md_file: Path, meta: dict[str, Any]):
        recorder.files_scanned += 1
        try:
            # Parsing is mostly CPU bound and tiny disk I/O, sync is fine
            # We run it in a thread if it's slow, but for now, it's ok.
            notes, skipped_indices, inventory = parser.parse_file(md_file, meta, cache, name_index)
            recorder.cards_generated += len(notes) + len(skipped_indices)
            recorder.cards_cached_content += len(inventory) - len(notes)

            recorder.add_inventory(inventory)

            for note in notes:
                wi = WorkItem(note=note, source_file=md_file, source_index=note.source_index)
                await work_q.put(wi)
        except Exception as e:
            logger.error(f"[producer-error] {md_file}: {e}")
            recorder.add_error(md_file, str(e))

    async def consumer():
        while True:
            item = await work_q.get()
            try:
                async with sync_semaphore:
                    batch_updates = await anki_bridge.sync_notes([item])

                async with updates_lock:
                    for u in batch_updates:
                        updates.append(u)
                        if u.ok:
                            recorder.cards_synced += 1
                            if u.note and u.note.content_hash:
                                cache.set_hash(u.source_file, u.source_index, u.note.content_hash)
                        else:
                            recorder.cards_failed += 1
                            recorder.add_error(
                                u.source_file, f"Sync fail: {u.error}", f"#{u.source_index}"
                            )
            except Exception as e:
                logger.error(f"[consumer-error] {e}")
                recorder.add_error(
                    item.source_file, f"Consumer crash: {e}", f"#{item.source_index}"
                )
            finally:
                work_q.task_done()

    # Create consumers
    consumers = [asyncio.create_task(consumer()) for _ in range(max_sync_concurrency)]

    # Run producers
    # Limit producer concurrency as well to avoid overwhelming memory if vault is huge
    prod_semaphore = asyncio.Semaphore(max(1, config.workers))

    async def bounded_producer(p, m):
        async with prod_semaphore:
            await producer_file(p, m)

    producer_tasks = [asyncio.create_task(bounded_producer(p, meta)) for (p, meta) in compatible]

    if use_tqdm:
        with tqdm(total=len(producer_tasks), desc="Processing", unit="file") as pbar:
            for coro in asyncio.as_completed(producer_tasks):
                await coro
                pbar.update(1)
                pbar.set_postfix(
                    {
                        "gen": recorder.cards_generated,
                        "ok": recorder.cards_synced,
                        "err": recorder.cards_failed,
                    }
                )
    else:
        await asyncio.gather(*producer_tasks)

    # Wait for all work to be processed
    await work_q.join()

    # Clean up consumers
    for c in consumers:
        c.cancel()

    # -------- Stage 4: Persist Updates (Write back NIDs) --------
    if updates:
        # Note: apply_updates is currently synchronous, but we can wrap it if needed.
        # It's a quick disk operation usually.
        logger.info("[pipeline] Persisting NIDs/CIDs to frontmatter...")
        vault_service.apply_updates(updates)

    # -------- Stage 5: Prune Orphans (Destructive) --------
    if config.prune:
        await _prune_orphans(config, recorder, anki_bridge, logger)

    total_generated = len(updates)
    total_imported = sum(1 for u in updates if u.ok)
    total_errors = len(recorder.errors)
    error_items = [u for u in updates if not u.ok]

    return RunStats(
        total_generated=total_generated,
        total_imported=total_imported,
        total_errors=total_errors,
        errors=error_items,
    )


async def _prune_orphans(
    config: AppConfig, recorder: RunRecorder, bridge: AnkiBridge, logger: logging.Logger
):
    if config.root_input != config.vault_root:
        logger.warning(
            "[prune] SKIPPED: Pruning requires running on the entire vault root to ensure safety."
        )
        return

    logger.info("[prune] analyzing vault vs anki state...")

    valid_nids = recorder.inventory_nids
    valid_decks = recorder.inventory_decks

    logger.debug(f"[prune] Found {len(valid_nids)} valid NIDs in inventory.")
    logger.debug(f"[prune] Found {len(valid_decks)} valid decks in inventory.")

    anki_decks = await bridge.get_deck_names()

    protected_decks = set(valid_decks)
    protected_decks = set(valid_decks)
    for d in valid_decks:
        deck_obj = AnkiDeck(name=d)
        protected_decks.update(deck_obj.parents)

    orphan_decks = []
    for d in anki_decks:
        if d not in protected_decks and d != "Default":
            orphan_decks.append(d)

    decks_to_scan = set(anki_decks) - {"Default"}
    if not decks_to_scan:
        logger.info("[prune] No non-default decks found.")
        return

    orphan_note_ids = []

    for d in decks_to_scan:
        if d in orphan_decks:
            continue

        deck_notes = await bridge.get_notes_in_deck(d)
        for nid_str, anki_id in deck_notes.items():
            if nid_str not in valid_nids:
                orphan_note_ids.append(anki_id)
                logger.debug(f"[prune] Identified orphan: nid={nid_str}, anki_id={anki_id} in {d}")
            else:
                logger.debug(f"[prune] Valid note confirmed: nid={nid_str} in {d}")

    n_decks = len(orphan_decks)
    n_notes = len(orphan_note_ids)

    if n_decks == 0 and n_notes == 0:
        logger.info("[prune] Clean. No orphans found.")
        return

    logger.warning("\n" + "=" * 40)
    logger.warning("PRUNE SUMMARY")
    logger.info(f"Valid NIDs found in vault: {len(valid_nids)}")
    logger.info(f"Valid Decks found in vault: {len(valid_decks)}")
    logger.warning("-" * 20)
    logger.warning(f"Orphan Decks to DELETE: {n_decks}")
    for d in orphan_decks:
        logger.warning(f"  - [DECK] {d}")
    logger.warning(f"Orphan Notes to DELETE: {n_notes}")
    if n_notes > 0:
        logger.warning(f"  - [NOTES] {n_notes} cards will be permanently removed.")

    if not config.force:
        # Use asyncio-friendly input if needed?
        # For CLI, standard input() is okay because the whole bridge is waiting here anyway.
        val = input("\nAre you sure you want to proceed? Type 'yes' to confirm: ")
        if val.lower() != "yes":
            logger.info("[prune] Aborted by user.")
            return

    if config.dry_run:
        logger.warning("[prune] DRY RUN: Destructive actions skipped.")
        return

    if n_notes > 0:
        logger.info(f"[prune] Deleting {n_notes} notes...")
        try:
            await bridge.delete_notes(orphan_note_ids)
        except Exception as e:
            logger.error(f"[prune] Failed to delete notes: {e}")

    if n_decks > 0:
        logger.info(f"[prune] Deleting {n_decks} decks...")
        try:
            await bridge.delete_decks(orphan_decks)
        except Exception as e:
            logger.error(f"[prune] Failed to delete decks: {e}")

    logger.info("[prune] Pruning complete.")

import logging
import platform
import sys
from pathlib import Path

from arete.application.config import AppConfig
from arete.application.factory import get_anki_bridge
from arete.application.parser import MarkdownParser
from arete.application.pipeline import RunStats, run_pipeline
from arete.application.utils.logging import setup_logging
from arete.application.vault_service import VaultService
from arete.infrastructure.persistence.cache import ContentCache


async def execute_sync(config: AppConfig) -> RunStats:
    """Core sync execution logic. Returns stats object instead of exiting."""
    logger, main_log_path, run_id = setup_logging(config.log_dir, config.verbose)
    logger.info(f"=== obsidian → anki (run_id={run_id}) ===")
    logger.info(f"System: {platform.system()} {platform.release()} ({platform.machine()})")
    logger.info(f"Python: {sys.version.split()[0]}")
    logger.info(f"anki_media_dir={config.anki_media_dir}")
    if config.anki_base:
        logger.info(f"anki_base={config.anki_base}")
    logger.info(f"vault_root={config.vault_root}")
    logger.info(f"Starting sync for vault: {config.vault_root}")
    logger.debug(
        f"[main] Config: root_input={config.root_input}, backend={config.backend}, "
        f"verbose={config.verbose}"
    )

    # 0. Initialize Services
    cache_path = Path(config.cache_db) if config.cache_db else None
    cache = ContentCache(db_path=cache_path)

    if config.clear_cache:
        logger.info("Clearing content cache as requested...")
        cache.clear()

    assert config.root_input is not None
    vault_service = VaultService(config.root_input, cache, ignore_cache=config.force)

    # These are guaranteed to be set by resolve_config
    assert config.vault_root is not None
    assert config.anki_media_dir is not None

    parser = MarkdownParser(
        config.vault_root,
        config.anki_media_dir,
        ignore_cache=config.force,
        default_deck=config.default_deck,
        logger=logger,
    )

    # Anki Adapter Selection

    anki_bridge = await get_anki_bridge(config)
    try:
        # Execute
        stats = await run_pipeline(
            config, logger, run_id, vault_service, parser, anki_bridge, cache
        )
        return stats
    finally:
        await anki_bridge.close()


async def run_sync_logic(config: AppConfig):
    """Orchestrates the sync process using the provided config."""
    stats = await execute_sync(config)

    # Re-acquire logger since execute_sync sets it up (or we could return it)
    # But usually setup_logging is global-ish or idempotent enough for this CLI usage.
    # Ideally we use the returned stats.
    # Note: execute_sync already logs the start. We might miss the logger instance here
    # if we wanted to log more, but setup_logging uses getLogger so it's fine.

    # We need to print the summary using the logger configured in execute_sync.
    # Ideally execute_sync logs the summary.

    # For now, let's keep the logging inside execute_sync or just print here?
    # execute_sync didn't log summary in my replacement above. Let's add it back there?
    # Actually, simpler to just logging here if we assume logging is setup.
    logger = logging.getLogger("arete.main")  # should match setup_logging root or specific

    logger.info(
        f"=== summary === generated={stats.total_generated} "
        f"updated/added={stats.total_imported} errors={stats.total_errors}"
    )

    if stats.total_errors and not config.keep_going:
        sys.exit(1)


def main():
    """Professional entry point that delegates to Typer."""
    from arete.interface.cli import app

    app()


if __name__ == "__main__":
    main()

import platform
import sys

from o2a.core.config import AppConfig
from o2a.core.pipeline import run_pipeline
from o2a.domain.interfaces import AnkiBridge
from o2a.infrastructure.cache import ContentCache
from o2a.logging_utils import setup_logging
from o2a.services.anki_apy import AnkiApyAdapter
from o2a.services.anki_connect import AnkiConnectAdapter
from o2a.services.parser import MarkdownParser
from o2a.services.vault import VaultService


async def run_sync_logic(config: AppConfig):
    """
    Orchestrates the sync process using the provided config.
    """
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

    # 0. Initialize Backendrvices
    cache = ContentCache()

    if config.clear_cache:
        logger.info("Clearing content cache as requested...")
        cache.clear()

    if config.root_input is None:
        raise ValueError("Root input must be set")
    vault_service = VaultService(config.root_input, cache, ignore_cache=config.force)

    # These are guaranteed to be set by resolve_config
    assert config.vault_root is not None
    assert config.anki_media_dir is not None

    parser = MarkdownParser(config.vault_root, config.anki_media_dir, logger)

    # Anki Adapter Selection
    anki_bridge: AnkiBridge

    # 1. Manual selection
    if config.backend == "ankiconnect":
        anki_bridge = AnkiConnectAdapter(url=config.anki_connect_url)
        if not await anki_bridge.is_responsive():
            logger.warning(
                "AnkiConnect selected but not responsive. "
                "Ensure Anki is running with AnkiConnect installed."
            )
    elif config.backend == "apy":
        anki_bridge = AnkiApyAdapter(
            apy_bin=config.apy_bin,
            anki_base=config.anki_base,
            move_deck=(not config.no_move_deck),
            dry_run=config.dry_run,
        )
    else:  # auto
        ac = AnkiConnectAdapter(url=config.anki_connect_url)
        if await ac.is_responsive():
            logger.info("AnkiConnect detected and responsive. Using AnkiConnect backend.")
            anki_bridge = ac
        else:
            logger.info("AnkiConnect not responsive. Falling back to apy.")
            anki_bridge = AnkiApyAdapter(
                apy_bin=config.apy_bin,
                anki_base=config.anki_base,
                move_deck=(not config.no_move_deck),
                dry_run=config.dry_run,
            )

    # Execute
    stats = await run_pipeline(config, logger, run_id, vault_service, parser, anki_bridge, cache)

    logger.info(
        f"=== summary === generated={stats.total_generated} "
        f"updated/added={stats.total_imported} errors={stats.total_errors}"
    )

    if stats.total_errors and not config.keep_going:
        sys.exit(1)


def main():
    """
    Professional entry point that delegates to Typer.
    """
    from o2a.cli import app

    app()


if __name__ == "__main__":
    main()

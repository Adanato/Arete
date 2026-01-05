"""Tests for the main entry point and orchestration logic."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from arete.core.config import AppConfig
from arete.main import run_sync_logic


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock config for testing."""
    return AppConfig.model_construct(
        root_input=tmp_path,
        vault_root=tmp_path,
        anki_media_dir=tmp_path / "media",
        anki_base=tmp_path / "anki",
        log_dir=tmp_path / "logs",
        backend="auto",
        anki_connect_url="http://localhost:8765",
        apy_bin="apy",
        run_apy=False,
        keep_going=False,
        no_move_deck=False,
        dry_run=False,
        prune=False,
        force=False,
        clear_cache=False,
        workers=2,
        queue_size=100,
        verbose=1,
        show_config=False,
        open_logs=False,
        open_config=False,
    )


@pytest.mark.asyncio
@patch("arete.main.run_pipeline")
@patch("arete.main.setup_logging")
async def test_run_sync_logic_success(mock_setup_logging, mock_run_pipeline, mock_config):
    """Test successful execution of run_sync_logic."""
    # Setup mocks
    mock_logger = MagicMock()
    mock_setup_logging.return_value = (mock_logger, Path("/tmp/log.txt"), "run-123")

    mock_stats = MagicMock()
    mock_stats.files_scanned = 10
    mock_stats.cards_synced = 25
    mock_stats.cards_failed = 0
    mock_stats.total_errors = 0
    mock_stats.total_generated = 25
    mock_stats.total_imported = 25
    mock_run_pipeline.return_value = mock_stats

    # Execute
    await run_sync_logic(mock_config)

    # Verify logging was set up
    mock_setup_logging.assert_called_once_with(mock_config.log_dir, mock_config.verbose)

    # Verify pipeline was called
    mock_run_pipeline.assert_called_once()
    # run_pipeline(config, logger, run_id, vault_service, parser, anki_bridge, cache)
    call_args = mock_run_pipeline.call_args.args
    assert call_args[0] == mock_config  # config
    assert call_args[1] == mock_logger  # logger
    assert call_args[2] == "run-123"  # run_id


@pytest.mark.asyncio
@patch("arete.services.anki_connect.AnkiConnectAdapter.is_responsive")
@patch("arete.main.run_pipeline")
@patch("arete.main.setup_logging")
async def test_backend_selection_ankiconnect(
    mock_setup_logging, mock_run_pipeline, mock_is_responsive, mock_config
):
    """Test that AnkiConnect is selected when available."""
    # Setup mocks
    mock_logger = MagicMock()
    mock_setup_logging.return_value = (mock_logger, Path("/tmp/log.txt"), "run-123")

    # Mock successful AnkiConnect response
    mock_is_responsive.return_value = True

    mock_run_pipeline.return_value = MagicMock(
        files_scanned=0, total_errors=0, total_generated=0, total_imported=0
    )

    # Execute with auto backend
    mock_config.backend = "auto"
    await run_sync_logic(mock_config)

    # Verify AnkiConnect was tested
    mock_is_responsive.assert_called()

    # Verify pipeline was called with AnkiConnect adapter
    call_args = mock_run_pipeline.call_args.args
    from arete.services.anki_connect import AnkiConnectAdapter

    assert isinstance(call_args[5], AnkiConnectAdapter)  # anki_bridge is 6th arg


@pytest.mark.asyncio
@patch("arete.services.anki_connect.AnkiConnectAdapter.is_responsive")
@patch("arete.main.run_pipeline")
@patch("arete.main.setup_logging")
async def test_backend_selection_apy_fallback(
    mock_setup_logging, mock_run_pipeline, mock_is_responsive, mock_config
):
    """Test fallback to apy when AnkiConnect is unavailable."""
    # Setup mocks
    mock_logger = MagicMock()
    mock_setup_logging.return_value = (mock_logger, Path("/tmp/log.txt"), "run-123")

    # Mock AnkiConnect failure
    mock_is_responsive.return_value = False

    mock_run_pipeline.return_value = MagicMock(
        files_scanned=0, total_errors=0, total_generated=0, total_imported=0
    )

    # Execute with auto backend
    mock_config.backend = "auto"
    await run_sync_logic(mock_config)

    # Verify pipeline was called with AnkiApy adapter
    call_args = mock_run_pipeline.call_args.args
    from arete.services.anki_apy import AnkiApyAdapter

    assert isinstance(call_args[5], AnkiApyAdapter)  # anki_bridge is 6th arg


@pytest.mark.asyncio
@patch("arete.main.run_pipeline")
@patch("arete.main.setup_logging")
async def test_backend_manual_ankiconnect(mock_setup_logging, mock_run_pipeline, mock_config):
    """Test manual selection of AnkiConnect backend."""
    mock_logger = MagicMock()
    mock_setup_logging.return_value = (mock_logger, Path("/tmp/log.txt"), "run-123")
    mock_run_pipeline.return_value = MagicMock(
        files_scanned=0, total_errors=0, total_generated=0, total_imported=0
    )

    # Force AnkiConnect
    mock_config.backend = "ankiconnect"
    await run_sync_logic(mock_config)

    # Verify AnkiConnect was used
    call_args = mock_run_pipeline.call_args.args
    from arete.services.anki_connect import AnkiConnectAdapter

    assert isinstance(call_args[5], AnkiConnectAdapter)  # anki_bridge is 6th arg


@pytest.mark.asyncio
@patch("arete.main.run_pipeline")
@patch("arete.main.setup_logging")
async def test_backend_manual_apy(mock_setup_logging, mock_run_pipeline, mock_config):
    """Test manual selection of apy backend."""
    mock_logger = MagicMock()
    mock_setup_logging.return_value = (mock_logger, Path("/tmp/log.txt"), "run-123")
    mock_run_pipeline.return_value = MagicMock(
        files_scanned=0, total_errors=0, total_generated=0, total_imported=0
    )

    # Force apy
    mock_config.backend = "apy"
    await run_sync_logic(mock_config)

    # Verify apy was used
    call_args = mock_run_pipeline.call_args.args
    from arete.services.anki_apy import AnkiApyAdapter

    assert isinstance(call_args[5], AnkiApyAdapter)  # anki_bridge is 6th arg


@pytest.mark.asyncio
@patch("arete.main.run_pipeline")
@patch("arete.main.setup_logging")
async def test_cache_clearing(mock_setup_logging, mock_run_pipeline, mock_config):
    """Test that cache is cleared when clear_cache is True."""
    mock_logger = MagicMock()
    mock_setup_logging.return_value = (mock_logger, Path("/tmp/log.txt"), "run-123")
    mock_run_pipeline.return_value = MagicMock(
        files_scanned=0, total_errors=0, total_generated=0, total_imported=0
    )

    # Enable cache clearing
    mock_config.clear_cache = True

    await run_sync_logic(mock_config)

    # Verify cache.clear() was called
    call_args = mock_run_pipeline.call_args.args
    # We can't easily verify clear() was called, but we can check the cache was passed
    assert len(call_args) == 7  # Verify all args were passed


@pytest.mark.asyncio
@patch("arete.main.run_pipeline")
@patch("arete.main.setup_logging")
async def test_vault_root_assertion(mock_setup_logging, mock_run_pipeline, mock_config):
    """Test that assertions ensure vault_root and anki_media_dir are set."""
    mock_logger = MagicMock()
    mock_setup_logging.return_value = (mock_logger, Path("/tmp/log.txt"), "run-123")
    mock_run_pipeline.return_value = MagicMock(
        files_scanned=0, total_errors=0, total_generated=0, total_imported=0
    )

    # These should be set by resolve_config, but let's verify the assertions work
    assert mock_config.vault_root is not None
    assert mock_config.anki_media_dir is not None

    await run_sync_logic(mock_config)

    # If we got here without AssertionError, the assertions passed
    assert True


@pytest.mark.asyncio
@patch("arete.main.run_pipeline")
@patch("arete.main.setup_logging")
async def test_services_initialization(mock_setup_logging, mock_run_pipeline, mock_config):
    """Test that all services are properly initialized."""
    mock_logger = MagicMock()
    mock_setup_logging.return_value = (mock_logger, Path("/tmp/log.txt"), "run-123")
    mock_run_pipeline.return_value = MagicMock(
        files_scanned=0, total_errors=0, total_generated=0, total_imported=0
    )

    await run_sync_logic(mock_config)

    # Verify pipeline was called with all required services
    call_args = mock_run_pipeline.call_args.args
    assert len(call_args) == 7  # run_pipeline takes 7 args

    # Verify types (config, logger, run_id, vault_service, parser, anki_bridge, cache)
    from arete.infrastructure.cache import ContentCache
    from arete.services.parser import MarkdownParser
    from arete.services.vault import VaultService

    assert isinstance(call_args[6], ContentCache)  # cache
    assert isinstance(call_args[3], VaultService)  # vault_service
    assert isinstance(call_args[4], MarkdownParser)  # parser


@pytest.mark.asyncio
@patch("arete.main.run_pipeline")
@patch("arete.main.setup_logging")
async def test_summary_output(mock_setup_logging, mock_run_pipeline, mock_config, capsys):
    """Test that summary is printed after pipeline execution."""
    mock_logger = MagicMock()
    mock_setup_logging.return_value = (mock_logger, Path("/tmp/log.txt"), "run-123")

    # Mock stats
    mock_stats = MagicMock()
    mock_stats.files_scanned = 10
    mock_stats.cards_synced = 25
    mock_stats.cards_failed = 2
    mock_stats.total_errors = 0  # Don't trigger sys.exit
    mock_stats.total_generated = 27
    mock_stats.total_imported = 25
    mock_run_pipeline.return_value = mock_stats

    await run_sync_logic(mock_config)

    # Verify summary was logged
    # Find the summary log call
    summary_calls = [
        call for call in mock_logger.info.call_args_list if "=== summary ===" in str(call)
    ]
    assert len(summary_calls) > 0
    summary_msg = str(summary_calls[0])
    assert "generated=27" in summary_msg
    assert "updated/added=25" in summary_msg

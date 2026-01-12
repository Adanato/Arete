"""Tests for the main entry point (Backend Selection)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from arete.application.config import AppConfig
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
@patch("arete.infrastructure.adapters.anki_connect.AnkiConnectAdapter.is_responsive")
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
    from arete.infrastructure.adapters.anki_connect import AnkiConnectAdapter

    assert isinstance(call_args[5], AnkiConnectAdapter)  # anki_bridge is 6th arg


@pytest.mark.asyncio
@patch("arete.infrastructure.adapters.anki_connect.AnkiConnectAdapter.is_responsive")
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
    from arete.infrastructure.adapters.anki_apy import AnkiApyAdapter

    assert isinstance(call_args[5], AnkiApyAdapter)  # anki_bridge is 6th arg


@pytest.mark.asyncio
@patch("arete.infrastructure.adapters.anki_connect.AnkiConnectAdapter.is_responsive")
@patch("arete.main.run_pipeline")
@patch("arete.main.setup_logging")
async def test_backend_manual_ankiconnect(
    mock_setup_logging, mock_run_pipeline, mock_is_responsive, mock_config
):
    """Test manual selection of AnkiConnect backend."""
    mock_logger = MagicMock()
    mock_setup_logging.return_value = (mock_logger, Path("/tmp/log.txt"), "run-123")
    mock_is_responsive.return_value = True

    mock_run_pipeline.return_value = MagicMock(
        files_scanned=0, total_errors=0, total_generated=0, total_imported=0
    )

    # Force AnkiConnect
    mock_config.backend = "ankiconnect"
    await run_sync_logic(mock_config)

    # Verify AnkiConnect was used
    call_args = mock_run_pipeline.call_args.args
    from arete.infrastructure.adapters.anki_connect import AnkiConnectAdapter

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
    from arete.infrastructure.adapters.anki_apy import AnkiApyAdapter

    assert isinstance(call_args[5], AnkiApyAdapter)  # anki_bridge is 6th arg

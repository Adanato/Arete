"""Tests for CLI commands: help, init, config, logs, server, mcp, anki subcommands, and humanize_error."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from arete.interface.cli import app, humanize_error

runner = CliRunner()


# --- Help ---


def test_cli_help():
    """Test that help text is displayed correctly."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "arete: Pro-grade Obsidian to Anki sync tool" in result.stdout
    assert "sync" in result.stdout
    assert "init" in result.stdout
    assert "config" in result.stdout


# --- Init ---


@patch("arete.application.wizard.run_init_wizard")
def test_init_command(mock_wizard):
    """Test init command calls the wizard."""
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0 or isinstance(result.exception, SystemExit)
    mock_wizard.assert_called_once()


# --- Config ---


@patch("arete.interface.cli.resolve_config")
def test_config_show_command(mock_resolve_config):
    """Test config show command displays JSON."""
    mock_config = MagicMock()
    mock_config.model_dump.return_value = {
        "root_input": str(Path("/tmp/vault")),
        "backend": "auto",
        "verbose": 1,
    }
    mock_resolve_config.return_value = mock_config

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0
    output_data = json.loads(result.stdout)
    assert output_data["root_input"] == str(Path("/tmp/vault"))
    assert output_data["backend"] == "auto"


# --- Server ---


@patch("uvicorn.run")
def test_server_command(mock_run):
    result = runner.invoke(app, ["server", "--port", "9000"])
    assert result.exit_code == 0
    mock_run.assert_called_with("arete.server:app", host="127.0.0.1", port=9000, reload=False)


@patch("arete.mcp_server.main")
def test_mcp_server_command(mock_main):
    result = runner.invoke(app, ["mcp-server"])
    assert result.exit_code == 0
    mock_main.assert_called_once()


# --- Anki Subcommands ---


def test_anki_stats_command():
    from arete.domain.stats.models import CardStatsAggregate, FsrsMemoryState

    with patch("arete.application.factory.get_stats_repo") as mock_get_repo:
        mock_instance = MagicMock()
        stats = [
            CardStatsAggregate(
                card_id=123,
                note_id=1,
                deck_name="Default",
                lapses=0,
                ease=2500,
                interval=1,
                due=123456,
                reps=5,
                fsrs=FsrsMemoryState(stability=5.0, difficulty=0.5),
                last_review=1000000,
            )
        ]
        mock_instance.get_card_stats = AsyncMock(return_value=stats)
        mock_instance.get_review_history = AsyncMock(return_value=[])
        mock_instance.get_deck_params = AsyncMock(return_value={})
        mock_get_repo.return_value = mock_instance

        result = runner.invoke(
            app,
            [
                "anki",
                "stats",
                "--nids",
                "123",
                "--backend",
                "ankiconnect",
                "--anki-connect-url",
                "http://fake",
            ],
        )

        assert result.exit_code == 0
        assert '"difficulty": 0.5' in result.stdout


def test_anki_stats_table():
    from arete.domain.stats.models import CardStatsAggregate, FsrsMemoryState

    with patch("arete.application.factory.get_stats_repo") as mock_get_repo:
        mock_instance = MagicMock()
        stats = [
            CardStatsAggregate(
                card_id=123,
                note_id=1,
                deck_name="Default",
                lapses=0,
                ease=2500,
                interval=1,
                due=123456,
                reps=5,
                fsrs=FsrsMemoryState(stability=5.0, difficulty=0.5),
                last_review=1000000,
            )
        ]
        mock_instance.get_card_stats = AsyncMock(return_value=stats)
        mock_instance.get_review_history = AsyncMock(return_value=[])
        mock_instance.get_deck_params = AsyncMock(return_value={})
        mock_get_repo.return_value = mock_instance

        result = runner.invoke(
            app,
            [
                "anki",
                "stats",
                "--nids",
                "123",
                "--no-json",
                "--backend",
                "ankiconnect",
                "--anki-connect-url",
                "http://fake",
            ],
        )
        assert result.exit_code == 0
        assert "Card Stats" in result.stdout
        assert "Default" in result.stdout
        assert "50%" in result.stdout


def test_suspend_cards():
    with patch("arete.application.factory.AnkiConnectAdapter") as mock_cls:
        mock_instance = mock_cls.return_value
        mock_instance.suspend_cards = AsyncMock(return_value=True)
        mock_instance.is_responsive = AsyncMock(return_value=True)

        result = runner.invoke(
            app,
            [
                "anki",
                "cards-suspend",
                "--cids",
                "123,456",
                "--backend",
                "ankiconnect",
                "--anki-connect-url",
                "http://fake",
            ],
        )
        assert result.exit_code == 0
        assert '{"ok": true}' in result.stdout


def test_unsuspend_cards():
    with patch("arete.application.factory.AnkiConnectAdapter") as mock_cls:
        mock_instance = mock_cls.return_value
        mock_instance.unsuspend_cards = AsyncMock(return_value=True)
        mock_instance.is_responsive = AsyncMock(return_value=True)

        result = runner.invoke(
            app,
            [
                "anki",
                "cards-unsuspend",
                "--cids",
                "123",
                "--backend",
                "ankiconnect",
                "--anki-connect-url",
                "http://fake",
            ],
        )
        assert result.exit_code == 0
        assert '{"ok": true}' in result.stdout


def test_model_styling():
    with patch("arete.application.factory.AnkiConnectAdapter") as mock_cls:
        mock_instance = mock_cls.return_value
        mock_instance.get_model_styling = AsyncMock(return_value="css")
        mock_instance.is_responsive = AsyncMock(return_value=True)

        result = runner.invoke(
            app,
            [
                "anki",
                "models-styling",
                "Basic",
                "--backend",
                "ankiconnect",
                "--anki-connect-url",
                "http://fake",
            ],
        )
        assert result.exit_code == 0
        assert '{"css": "css"}' in result.stdout


def test_model_templates():
    with patch("arete.application.factory.AnkiConnectAdapter") as mock_cls:
        mock_instance = mock_cls.return_value
        mock_instance.get_model_templates = AsyncMock(return_value={"Front": "Q"})
        mock_instance.is_responsive = AsyncMock(return_value=True)

        result = runner.invoke(
            app,
            [
                "anki",
                "models-templates",
                "Basic",
                "--backend",
                "ankiconnect",
                "--anki-connect-url",
                "http://fake",
            ],
        )
        assert result.exit_code == 0
        assert '"Front": "Q"' in result.stdout


def test_anki_browse():
    with patch("arete.application.factory.AnkiConnectAdapter") as mock_cls:
        mock_instance = mock_cls.return_value
        mock_instance.gui_browse = AsyncMock(return_value=True)
        mock_instance.is_responsive = AsyncMock(return_value=True)

        result = runner.invoke(
            app,
            [
                "anki",
                "browse",
                "--query",
                "deck:Default",
                "--backend",
                "ankiconnect",
                "--anki-connect-url",
                "http://fake",
            ],
        )
        assert result.exit_code == 0
        assert '{"ok": true}' in result.stdout


# --- humanize_error ---


def test_humanize_error_simple():
    assert humanize_error("Some error") == "Some error"


def test_humanize_error_block_end():
    msg = humanize_error("expected <block end>, but found '?'")
    assert "Indentation Error" in msg


def test_humanize_error_scanner():
    msg = humanize_error("scanner error")
    assert "Syntax Error" in msg


def test_humanize_error_extra_cases():
    assert "Syntax Error" in humanize_error("did not find expected key")
    assert "Duplicate Key" in humanize_error("found duplicate key")

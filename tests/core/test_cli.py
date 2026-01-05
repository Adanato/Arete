"""Tests for the Typer CLI interface."""

import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from o2a.cli import app

runner = CliRunner()


def test_cli_help():
    """Test that help text is displayed correctly."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "o2a: Pro-grade Obsidian to Anki sync tool" in result.stdout
    assert "sync" in result.stdout
    assert "init" in result.stdout
    assert "config" in result.stdout


def strip_ansi(text):
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def test_sync_command_help():
    """Test sync command help text."""
    result = runner.invoke(app, ["sync", "--help"])
    assert result.exit_code == 0
    # Strip ANSI codes (e.g. from Rich) before asserting text content
    output = strip_ansi(result.stdout)
    assert "Sync your Obsidian notes to Anki" in output
    assert "--prune" in output
    assert "--backend" in output


@patch("asyncio.run")
@patch("o2a.cli.resolve_config")
def test_sync_command_basic(mock_resolve_config, mock_asyncio_run):
    """Test basic sync command execution."""
    # Mock config
    mock_config = MagicMock()
    mock_resolve_config.return_value = mock_config

    # Mock async execution
    mock_asyncio_run.return_value = None

    result = runner.invoke(app, ["sync", "/tmp/vault"])

    assert result.exit_code == 0
    mock_resolve_config.assert_called_once()
    mock_asyncio_run.assert_called_once()

    # Verify config overrides
    call_args = mock_resolve_config.call_args[0][0]
    expected_path = str(Path("/tmp/vault"))
    assert str(call_args["root_input"]) == expected_path


@patch("asyncio.run")
@patch("o2a.cli.resolve_config")
def test_sync_command_with_flags(mock_resolve_config, mock_asyncio_run):
    """Test sync command with various flags."""
    mock_config = MagicMock()
    mock_resolve_config.return_value = mock_config
    mock_asyncio_run.return_value = None

    result = runner.invoke(
        app,
        [
            "sync",
            "/tmp/vault",
            "--prune",
            "--force",
            "--dry-run",
            "--backend",
            "ankiconnect",
            "--workers",
            "4",
        ],
    )

    assert result.exit_code == 0

    call_args = mock_resolve_config.call_args[0][0]
    assert call_args["prune"] is True
    assert call_args["force"] is True
    assert call_args["dry_run"] is True
    assert call_args["backend"] == "ankiconnect"
    assert call_args["workers"] == 4


@patch("asyncio.run")
@patch("o2a.cli.resolve_config")
def test_sync_command_verbose_flag(mock_resolve_config, mock_asyncio_run):
    """Test verbose flag increments verbosity."""
    mock_config = MagicMock()
    mock_resolve_config.return_value = mock_config
    mock_asyncio_run.return_value = None

    # Test -v
    result = runner.invoke(app, ["-v", "sync", "."])
    assert result.exit_code == 0
    call_args = mock_resolve_config.call_args[0][0]
    assert call_args["verbose"] == 1

    # Test -vv
    result = runner.invoke(app, ["-v", "-v", "sync", "."])
    assert result.exit_code == 0
    call_args = mock_resolve_config.call_args[0][0]
    assert call_args["verbose"] == 2


@patch("o2a.core.wizard.run_init_wizard")
def test_init_command(mock_wizard):
    """Test init command calls the wizard."""
    result = runner.invoke(app, ["init"])

    # Typer raises Exit after wizard, which is expected
    assert result.exit_code == 0 or isinstance(result.exception, SystemExit)
    mock_wizard.assert_called_once()


@patch("o2a.cli.resolve_config")
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
    # Verify JSON output
    output_data = json.loads(result.stdout)
    assert output_data["root_input"] == str(Path("/tmp/vault"))
    assert output_data["backend"] == "auto"


@patch("subprocess.run")
def test_config_open_command_macos(mock_subprocess):
    """Test config open command on macOS."""
    with patch("sys.platform", "darwin"):
        result = runner.invoke(app, ["config", "open"])

        assert result.exit_code == 0
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args[0][0]
        assert call_args[0] == "open"
        # On Windows host, Path(...) will produce backslashes even if stripped.
        # We verify that the *parts* match to avoid separator issues.
        # But here we are mocking subprocess so the arg is effectively `str(path)`.
        # The key is checking if ".config" and "o2a" are in there.
        arg_str = str(call_args[1])
        assert ".config" in arg_str and "o2a" in arg_str and "config.toml" in arg_str


@patch("subprocess.run")
@patch("o2a.cli.resolve_config")
def test_logs_command(mock_resolve_config, mock_subprocess):
    """Test logs command opens log directory."""
    mock_config = MagicMock()
    mock_config.log_dir = Path("/tmp/logs")
    mock_resolve_config.return_value = mock_config

    with patch("sys.platform", "darwin"):
        result = runner.invoke(app, ["logs"])

        assert result.exit_code == 0
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args[0][0]
        assert call_args[0] == "open"
        assert str(call_args[1]) == str(Path("/tmp/logs"))


@patch("asyncio.run")
@patch("o2a.cli.resolve_config")
def test_sync_command_no_path_uses_cwd(mock_resolve_config, mock_asyncio_run):
    """Test sync without path argument defaults to CWD."""
    mock_config = MagicMock()
    mock_resolve_config.return_value = mock_config
    mock_asyncio_run.return_value = None

    result = runner.invoke(app, ["sync"])

    assert result.exit_code == 0
    call_args = mock_resolve_config.call_args[0][0]
    # When no path is provided, root_input should not be in overrides
    assert "root_input" not in call_args or call_args["root_input"] is None


@patch("asyncio.run")
@patch("o2a.cli.resolve_config")
def test_sync_command_anki_connect_url(mock_resolve_config, mock_asyncio_run):
    """Test custom AnkiConnect URL."""
    mock_config = MagicMock()
    mock_resolve_config.return_value = mock_config
    mock_asyncio_run.return_value = None

    result = runner.invoke(app, ["sync", ".", "--anki-connect-url", "http://custom:9999"])

    assert result.exit_code == 0
    call_args = mock_resolve_config.call_args[0][0]
    assert call_args["anki_connect_url"] == "http://custom:9999"


@patch("asyncio.run")
@patch("o2a.cli.resolve_config")
def test_sync_command_clear_cache(mock_resolve_config, mock_asyncio_run):
    """Test --clear-cache flag."""
    mock_config = MagicMock()
    mock_resolve_config.return_value = mock_config
    mock_asyncio_run.return_value = None

    result = runner.invoke(app, ["sync", ".", "--clear-cache"])

    assert result.exit_code == 0
    call_args = mock_resolve_config.call_args[0][0]
    assert call_args["clear_cache"] is True

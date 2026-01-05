import sys
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from o2a.cli import app

runner = CliRunner()


def test_cli_config_show():
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "vault_root" in result.stdout


def test_cli_config_open():
    with (
        patch("subprocess.run") as mock_run,
        patch.object(sys, "platform", "linux"),
    ):
        result = runner.invoke(app, ["config", "open"])
        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_cli_config_open_windows():
    with (
        patch("os.startfile", create=True) as mock_startfile,
        patch.object(sys, "platform", "win32"),
    ):
        result = runner.invoke(app, ["config", "open"])
        assert result.exit_code == 0
        mock_startfile.assert_called_once()


def test_cli_logs_open():
    with (
        patch("subprocess.run") as mock_run,
        patch.object(sys, "platform", "linux"),
    ):
        result = runner.invoke(app, ["logs"])
        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_cli_logs_open_windows():
    with (
        patch("os.startfile", create=True) as mock_startfile,
        patch.object(sys, "platform", "win32"),
    ):
        result = runner.invoke(app, ["logs"])
        assert result.exit_code == 0
        mock_startfile.assert_called_once()


def test_cli_init_mock():
    with patch("o2a.core.wizard.run_init_wizard") as mock_wizard:
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        mock_wizard.assert_called_once()


def test_cli_check_file(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\nanki_template_version: 1\n---\n")

    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 0
    assert "Valid o2a file" in result.stdout


def test_cli_check_file_json(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\nanki_template_version: 1\n---\n")

    result = runner.invoke(app, ["check-file", str(f), "--json"])
    assert result.exit_code == 0
    assert '"ok": true' in result.stdout


def test_cli_check_file_error_yaml(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\nbad_yaml: : :\n---\n")

    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 1
    assert "Validation Failed" in result.stdout


def test_cli_check_file_not_found():
    result = runner.invoke(app, ["check-file", "nonexistent.md"])
    assert result.exit_code == 1
    assert "File not found" in result.stdout


def test_cli_check_file_not_list(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\ncards: not_a_list\n---\n")
    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 1
    assert "Expected a list" in result.stdout


def test_cli_check_file_invalid_card_type(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\ncards:\n  - not_a_dict\n---\n")
    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 1
    assert "Expected a dictionary" in result.stdout


def test_cli_check_file_empty_card(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\ncards:\n  - {}\n---\n")
    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 1
    assert "is empty" in result.stdout


def test_cli_check_file_missing_fields(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\ncards:\n  - Back: only back\n---\n")
    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 1
    assert "Missing 'Front'?" in result.stdout


def test_cli_check_file_inconsistent_front(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\ncards:\n  - Front: f1\n  - Back: b2\n---\n")
    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 1
    assert "missing 'Front' field" in result.stdout


def test_cli_check_file_inconsistent_text(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\ncards:\n  - Text: t1\n  - Back: b2\n---\n")
    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 1
    assert "missing 'Text' field" in result.stdout


def test_cli_check_file_humanize_tab(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\nkey:\tval\n---\n")
    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 1
    assert "Tab Character Error" in result.stdout


def test_cli_sync_mock(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()

    with patch("o2a.main.run_sync_logic", new_callable=AsyncMock) as mock_sync:
        result = runner.invoke(app, ["sync", str(vault)])
        assert result.exit_code == 0
        mock_sync.assert_called_once()


def test_cli_fix_file(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\nkey:\telement\n---\n")

    result = runner.invoke(app, ["fix-file", str(f)])
    assert result.exit_code == 0
    assert "auto-fixed" in result.stdout


def test_cli_fix_file_no_changes(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\nkey: val\n---\n")

    result = runner.invoke(app, ["fix-file", str(f)])
    assert result.exit_code == 0
    assert "No fixable issues found" in result.stdout


def test_cli_fix_file_not_found():
    result = runner.invoke(app, ["fix-file", "nonexistent.md"])
    assert result.exit_code == 1
    assert "File not found" in result.stdout

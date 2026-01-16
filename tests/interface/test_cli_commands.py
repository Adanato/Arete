from unittest.mock import patch

from typer.testing import CliRunner

from arete.interface.cli import app

runner = CliRunner()


@patch("uvicorn.run")
def test_server_command(mock_run):
    result = runner.invoke(app, ["server", "--port", "9000"])
    assert result.exit_code == 0
    mock_run.assert_called_with("arete.server:app", host="127.0.0.1", port=9000, reload=False)


@patch("subprocess.run")
@patch("sys.platform", "darwin")
def test_logs_command_mac(mock_sub):
    with patch("arete.interface.cli.resolve_config") as mock_conf:
        mock_conf.return_value.log_dir.exists.return_value = True
        result = runner.invoke(app, ["logs"])
        assert result.exit_code == 0
        mock_sub.assert_called()
        assert mock_sub.call_args[0][0][0] == "open"


@patch("subprocess.run")
@patch("sys.platform", "linux")
def test_logs_command_linux(mock_sub):
    with patch("arete.interface.cli.resolve_config") as mock_conf:
        mock_conf.return_value.log_dir.exists.return_value = True
        result = runner.invoke(app, ["logs"])
        assert result.exit_code == 0
        mock_sub.assert_called()
        assert mock_sub.call_args[0][0][0] == "xdg-open"


def test_fix_file_not_found():
    result = runner.invoke(app, ["fix-file", "missing.md"])
    assert result.exit_code == 1
    assert "File not found" in result.stdout


def test_fix_file_already_clean(tmp_path):
    f = tmp_path / "clean.md"
    f.write_text("---\nfoo: bar\n---\n")
    # Patch SOURCE because CLI imports it inside function
    # Note: 'arete.infrastructure.utils.text.validate_frontmatter' is what we patch
    with patch("arete.infrastructure.utils.text.validate_frontmatter", return_value={"foo": "bar"}):
        result = runner.invoke(app, ["fix-file", str(f)])
        assert result.exit_code == 0
        assert "No fixable issues found" in result.stdout


def test_fix_file_apply_fix(tmp_path):
    f = tmp_path / "dirty.md"
    f.write_text("---\nfoo:\tbar\n---\n")

    result = runner.invoke(app, ["fix-file", str(f)])
    assert result.exit_code == 0
    assert "File auto-fixed" in result.stdout
    assert "foo:  bar" in f.read_text()


@patch("arete.mcp_server.main")
def test_mcp_server_command(mock_main):
    result = runner.invoke(app, ["mcp-server"])
    assert result.exit_code == 0
    mock_main.assert_called_once()

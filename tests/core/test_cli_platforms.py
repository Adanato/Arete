from unittest.mock import ANY, patch

from typer.testing import CliRunner

from arete.cli import app

runner = CliRunner()


def test_config_open_create_if_missing():
    with (
        patch("pathlib.Path.exists", return_value=False),
        patch("pathlib.Path.mkdir") as mock_mkdir,
        patch("pathlib.Path.touch") as mock_touch,
        patch("subprocess.run"),
        patch("sys.platform", "darwin"),
    ):
        result = runner.invoke(app, ["config", "open"])
        assert result.exit_code == 0
        mock_mkdir.assert_called()
        mock_touch.assert_called()


def test_config_open_win32():
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("os.startfile", create=True) as mock_start,
        patch("sys.platform", "win32"),
    ):
        result = runner.invoke(app, ["config", "open"])
        assert result.exit_code == 0
        mock_start.assert_called()


def test_config_open_linux():
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("subprocess.run") as mock_run,
        patch("sys.platform", "linux"),
    ):
        result = runner.invoke(app, ["config", "open"])
        assert result.exit_code == 0
        mock_run.assert_called_with(["xdg-open", ANY])


def test_logs_mkdir_and_open_win32():
    with patch("arete.cli.resolve_config") as mock_conf:
        mock_conf.return_value.log_dir.exists.return_value = False

        with patch("sys.platform", "win32"), patch("os.startfile", create=True) as mock_start:
            result = runner.invoke(app, ["logs"])
            assert result.exit_code == 0
            mock_conf.return_value.log_dir.mkdir.assert_called()
            mock_start.assert_called()


def test_logs_linux():
    with patch("arete.cli.resolve_config") as mock_conf:
        mock_conf.return_value.log_dir.exists.return_value = True

        with patch("sys.platform", "linux"), patch("subprocess.run") as mock_run:
            result = runner.invoke(app, ["logs"])
            assert result.exit_code == 0
            mock_run.assert_called()


def test_humanize_error_extra_cases():
    from arete.cli import humanize_error

    assert "Syntax Error" in humanize_error("did not find expected key")
    assert "Duplicate Key" in humanize_error("found duplicate key")
    assert "Syntax Error" in humanize_error("scanner error")

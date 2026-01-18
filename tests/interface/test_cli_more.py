from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from arete.application.config import AppConfig
from arete.domain.stats.models import CardStatsAggregate, FsrsMemoryState
from arete.interface.cli import app

runner = CliRunner()


@pytest.fixture
def mock_config():
    return AppConfig(
        vault_root=Path("/tmp"), anki_media_dir=Path("/tmp/media"), log_dir=Path("/tmp/logs")
    )


def test_config_show(tmp_path):
    with patch("arete.interface.cli.resolve_config") as mock_resolve:
        mock_resolve.return_value = AppConfig(vault_root=tmp_path)
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "vault_root" in result.stdout


def test_config_open():
    # cli.py uses subprocess.run(["open", ...], ...) on darwin
    # We assume test runs on darwin or linux.
    with patch("subprocess.run") as mock_run:
        # We also need to mock sys.platform if we want deterministic behavior,
        # but let's assume valid platform flow or mock os.startfile if needed.
        # cli.py handles win32 separately.

        with patch("arete.interface.cli.sys.platform", "darwin"):
            result = runner.invoke(app, ["config", "open"])
            assert result.exit_code == 0
            mock_run.assert_called_once()


def test_logs_open(mock_config):
    # Logs command uses resolve_config, not setup_logging
    with patch("arete.interface.cli.resolve_config") as mock_resolve:
        mock_resolve.return_value = mock_config
        with patch("subprocess.run") as mock_run:
            with patch("arete.interface.cli.sys.platform", "darwin"):
                result = runner.invoke(app, ["logs"])
                assert result.exit_code == 0
                mock_run.assert_called_once()
                # Check arg is log_dir
                args, _ = mock_run.call_args
                assert str(mock_config.log_dir) in args[0]


def test_check_file(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\narete: true\ndeck: Default\ncards:\n  - Front: Q\n    Back: A\n---\n")

    # check-file command (hyphenated).
    # It requires valid frontmatter to pass 0 exit code.
    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 0
    assert "Valid arete file" in result.stdout


def test_humanize_error():
    from arete.interface.cli import humanize_error

    msg = humanize_error("scanner error")
    assert "Syntax Error: scanner error" in msg


def test_migrate_dry_run(tmp_path):
    # migrate command
    result = runner.invoke(app, ["migrate", str(tmp_path), "--dry-run"])
    assert result.exit_code == 0


# Removed @pytest.mark.asyncio to avoid nested event loop with runner.invoke -> asyncio.run
def test_anki_stats_command():
    # anki stats command
    # calls asyncio.run(run())

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

        # We also need factory to actually USE this class.
        # If backend=None, factory checks is_responsive.
        # If we pass backend=ankiconnect, it forces usage.

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
        if result.exit_code != 0:
            print(result.stdout)
            print(result.exception)

        assert result.exit_code == 0
        assert '"difficulty": 0.5' in result.stdout


def test_fix_file(tmp_path):
    f = tmp_path / "broken.md"
    # fix_file requires frontmatter to match regex.
    # Introduce a tab in frontmatter which is invalid.
    f.write_text("---\ndeck:\tTabbed\ncards: []\n---\n")
    result = runner.invoke(app, ["fix-file", str(f)])
    assert result.exit_code == 0
    assert "File auto-fixed" in result.stdout
    assert "Replaced tabs" in result.stdout


def test_migrate_yaml_error(tmp_path):
    p = tmp_path / "fail.md"
    p.write_text("---\narete: true\ninvalid: [\n---\nBody", encoding="utf-8")

    from typer.testing import CliRunner

    from arete.interface.cli import app

    runner = CliRunner()

    # We need to set verbose to 2 to see the parse error line 648
    result = runner.invoke(app, ["migrate", str(tmp_path), "-vv"])
    assert result.exit_code == 0


def test_migrate_skip(tmp_path):
    p = tmp_path / "skip.md"
    p.write_text("---\nother: true\n---\nBody", encoding="utf-8")

    from arete.interface.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["migrate", str(tmp_path), "-vvv"])
    assert result.exit_code == 0


def test_migrate_redundant_frontmatter(tmp_path):
    p = tmp_path / "redundant.md"
    # Content with redundant --- block after frontmatter
    p.write_text("---\narete: true\n---\n---\n Body\n", encoding="utf-8")

    from arete.interface.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["migrate", str(tmp_path)])
    assert result.exit_code == 0
    content = p.read_text(encoding="utf-8")
    # Should have stripped the second --- block and normalized
    assert content.count("---") == 2


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


def test_anki_stats_table():
    # Test table output (no-json)
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

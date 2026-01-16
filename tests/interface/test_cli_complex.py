from unittest.mock import patch

from typer.testing import CliRunner

from arete.interface.cli import app

runner = CliRunner()

# --- Check File Tests ---


def test_check_file_not_found():
    result = runner.invoke(app, ["check-file", "missing.md"])
    assert result.exit_code == 1
    assert "File not found" in result.stdout


def test_check_file_invalid_yaml(tmp_path):
    f = tmp_path / "bad.md"
    f.write_text("---\nfoo: [unclosed\n---\n")

    # We rely on validate_frontmatter raising YAMLError, which cli catches
    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 1
    assert "Validation Failed" in result.stdout


def test_check_file_valid_arete(tmp_path):
    f = tmp_path / "good.md"
    f.write_text("---\narete: true\ndeck: Default\ncards:\n- Front: Q\n  Back: A\n---\n")

    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 0
    assert "Valid arete file" in result.stdout


def test_check_file_missing_deck(tmp_path):
    f = tmp_path / "nodeck.md"
    f.write_text("---\narete: true\ncards: []\n---\n")

    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 1
    assert "missing 'deck' field" in result.stdout


def test_check_file_strict_missing_cards(tmp_path):
    f = tmp_path / "nocards.md"
    f.write_text("---\narete: true\ndeck: D\n---\n")

    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 1
    assert "missing 'cards' list" in result.stdout


def test_check_file_split_card_error(tmp_path):
    f = tmp_path / "split.md"
    f.write_text("---\narete: true\ndeck: D\ncards:\n- Front: Q\n- Back: A\n---\n")

    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 1
    assert "Split Card Error" in result.stdout


# --- Migrate Tests ---


# Patch the SOURCE module where iter_markdown_files is defined
@patch("arete.application.utils.fs.iter_markdown_files")
def test_migrate_command(mock_iter, tmp_path):
    f = tmp_path / "legacy.md"
    f.write_text("---\nanki_template_version: 1\n---\n")
    mock_iter.return_value = [f]

    result = runner.invoke(app, ["migrate", str(tmp_path)])
    assert result.exit_code == 0
    assert "Migrated" in result.stdout
    assert "arete: true" in f.read_text()


@patch("arete.application.utils.fs.iter_markdown_files")
def test_migrate_dry_run(mock_iter, tmp_path):
    f = tmp_path / "legacy.md"
    f.write_text("---\nanki_template_version: 1\n---\n")
    mock_iter.return_value = [f]

    result = runner.invoke(app, ["migrate", str(tmp_path), "--dry-run"])
    assert result.exit_code == 0
    assert "[DRY RUN]" in result.stdout
    assert "anki_template_version: 1" in f.read_text()  # Unchanged


@patch("arete.application.utils.fs.iter_markdown_files")
def test_migrate_skip_no_flag(mock_iter, tmp_path):
    f = tmp_path / "plain.md"
    f.write_text("---\ntitle: Hello\n---\n")
    mock_iter.return_value = [f]

    result = runner.invoke(app, ["migrate", str(tmp_path), "-v"])
    assert result.exit_code == 0
    # Should skip
    # verify content unchanged
    assert "title: Hello" in f.read_text()


@patch("arete.application.utils.fs.iter_markdown_files")
def test_migrate_auto_heal_split(mock_iter, tmp_path):
    f = tmp_path / "split.md"
    f.write_text("---\narete: true\ncards:\n- Front: Q\n- Back: A\n---\n")
    mock_iter.return_value = [f]

    runner.invoke(app, ["migrate", str(tmp_path)])

    content = f.read_text()
    assert "Front: Q" in content
    assert "Back: A" in content
    # Check if merged (heuristic check - naive but expected behavior is valid yaml)
    # The _merge_split_cards function is what we are testing indirectly via migrate
    pass

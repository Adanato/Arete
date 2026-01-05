import json

from typer.testing import CliRunner

from arete.cli import app

runner = CliRunner()


def test_check_file_valid_basic(tmp_path):
    """1. Test a perfectly valid file."""
    f = tmp_path / "valid.md"
    f.write_text(
        "---\ndeck: Default\ncards:\n  - Front: A\n    Back: B\n---\nContent", encoding="utf-8"
    )

    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 0
    assert "✅ Valid arete file!" in result.stdout
    assert "Cards: 1" in result.stdout


def test_check_file_valid_minimal(tmp_path):
    """2. Test a valid file with just version info (no cards required if no deck/model)."""
    f = tmp_path / "minimal.md"
    f.write_text("---\nanki_template_version: 1\n---\nContent", encoding="utf-8")

    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 0
    assert "✅ Valid arete file!" in result.stdout


def test_check_file_yaml_syntax_error(tmp_path):
    """3. Test invalid YAML syntax (bad indentation)."""
    f = tmp_path / "bad_syntax.md"
    f.write_text("---\ndeck: D\n  bad_indent: v\n---\n", encoding="utf-8")

    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 1
    assert "❌ Validation Failed" in result.stdout
    # Now returns friendly "Indentation Error"
    assert "Indentation Error" in result.stdout


def test_check_file_yaml_scanner_error(tmp_path):
    """4. Test another type of YAML error (broken mapping)."""
    f = tmp_path / "broken.md"
    f.write_text("---\nkey: : value\n---\n", encoding="utf-8")

    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 1
    assert "Validation Failed" in result.stdout


def test_check_file_missing_cards_with_deck(tmp_path):
    """5. Test missing 'cards' when 'deck' is present."""
    f = tmp_path / "no_cards.md"
    f.write_text("---\ndeck: Default\n---\n", encoding="utf-8")

    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 1
    # Updated message
    assert "Missing 'cards' list" in result.stdout


def test_check_file_missing_cards_with_model(tmp_path):
    """6. Test missing 'cards' when 'model' is present."""
    f = tmp_path / "no_cards_model.md"
    f.write_text("---\nmodel: Basic\n---\n", encoding="utf-8")

    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 1
    assert "Missing 'cards' list" in result.stdout


def test_check_file_file_not_found():
    """7. Test non-existent file path."""
    result = runner.invoke(app, ["check-file", "non_existent.md"])
    assert result.exit_code == 1
    assert "File not found" in result.stdout


def test_check_file_no_frontmatter(tmp_path):
    """8. Test file without frontmatter (should be valid but empty usage)."""
    f = tmp_path / "plain.md"
    f.write_text("# Just Markdown", encoding="utf-8")

    result = runner.invoke(app, ["check-file", str(f)])
    # Currently considered valid (just ignored by arete)
    assert result.exit_code == 0
    assert "✅ Valid arete file!" in result.stdout


def test_check_file_json_output_failure(tmp_path):
    """9. Test JSON output format on failure."""
    f = tmp_path / "bad.md"
    f.write_text("---\ndeck: D\n  bad: i\n---\n", encoding="utf-8")

    result = runner.invoke(app, ["check-file", str(f), "--json"])
    assert result.exit_code == 0

    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert len(data["errors"]) > 0
    assert data["errors"][0]["line"] > 0


def test_check_file_json_output_success(tmp_path):
    """10. Test JSON output format on success."""
    f = tmp_path / "good.md"
    f.write_text("---\ndeck: D\ncards: []\n---\n", encoding="utf-8")

    result = runner.invoke(app, ["check-file", str(f), "--json"])
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["stats"]["deck"] == "D"


def test_check_file_tab_handling(tmp_path):
    """11. Test that tabs in frontmatter are flagged as errors (Obsidian compatibility)."""
    f = tmp_path / "tabs.md"
    f.write_text("---\ndeck: Default\ncards:\n\t- Front: A\n\t  Back: B\n---\n", encoding="utf-8")

    result = runner.invoke(app, ["check-file", str(f)])
    # Strict mode: Should fail now
    assert result.exit_code == 1
    assert "Tab Character Error" in result.stdout


def test_check_file_duplicate_keys(tmp_path):
    """12. Test that duplicate keys are flagged as errors."""
    f = tmp_path / "dupe.md"
    f.write_text("---\ndeck: A\ndeck: B\n---\n", encoding="utf-8")

    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 1
    assert "Duplicate Key Error" in result.stdout

from typer.testing import CliRunner

from arete.interface.cli import app

runner = CliRunner()


def test_check_file_not_found():
    result = runner.invoke(app, ["check-file", "nonexistent.md"])
    assert result.exit_code == 1
    assert "File not found." in result.stdout


def test_check_file_valid(tmp_path):
    f = tmp_path / "test.md"
    f.write_text(
        "---\narete: true\ndeck: Default\ncards:\n  - Front: Q\n    Back: A\n---\n# Test",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 0
    assert "Valid arete file!" in result.stdout


def test_check_file_invalid_yaml(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\narete: true\ncards: [\n---\n# Test", encoding="utf-8")
    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 1
    assert "Validation Failed" in result.stdout


def test_fix_file_no_changes(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("# Test", encoding="utf-8")
    result = runner.invoke(app, ["fix-file", str(f)])
    assert result.exit_code == 0
    assert "No fixable issues found" in result.stdout


def test_fix_file_replaces_tabs(tmp_path):
    f = tmp_path / "test.md"
    # apply_fixes needs frontmatter to trigger tab replacement
    f.write_text("---\ndeck: Default\n\t- card :: back\n---\n# Test", encoding="utf-8")
    result = runner.invoke(app, ["fix-file", str(f)])
    assert result.exit_code == 0
    assert "File auto-fixed!" in result.stdout
    assert "\t" not in f.read_text()


def test_migrate_dry_run(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("anki_template_version: 1\n# Test", encoding="utf-8")
    result = runner.invoke(app, ["migrate", str(tmp_path), "--dry-run"])
    assert result.exit_code == 0
    assert "DRY RUN" in result.stdout
    assert "anki_template_version" in f.read_text()


def test_migrate_apply(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("anki_template_version: 1\ncards: []\n# Test", encoding="utf-8")
    result = runner.invoke(app, ["migrate", str(tmp_path)])
    assert result.exit_code == 0
    assert "Migrated" in result.stdout
    assert "arete: true" in f.read_text()

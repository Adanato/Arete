from unittest.mock import patch

from typer.testing import CliRunner
from yaml import YAMLError
from yaml.error import Mark

from arete.cli import app

runner = CliRunner()


def test_check_file_not_found_json():
    result = runner.invoke(app, ["check-file", "nonexistent.md", "--json"])
    assert result.exit_code == 1
    assert '"ok": false' in result.stdout
    assert "File not found." in result.stdout


def test_check_file_yaml_error_context(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\nfoo: bar\n---\n")

    # Mock YAMLError with context
    err = YAMLError()
    err.problem_mark = Mark("name", 0, 0, 0, "", 0)  # type: ignore
    err.problem = "problem"  # type: ignore
    err.context = "context_info"  # type: ignore

    with patch("arete.text.validate_frontmatter", side_effect=err):
        result = runner.invoke(app, ["check-file", str(f)])
        assert result.exit_code == 1
        assert "context_info" in result.stdout


def test_check_file_generic_exception(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("content")

    with patch("arete.text.validate_frontmatter", side_effect=Exception("Generic Error")):
        result = runner.invoke(app, ["check-file", str(f), "--json"])
        assert result.exit_code == 0
        assert "Generic Error" in result.stdout


def test_check_file_missing_cards(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("---\ndeck: Default\n---\n")

    result = runner.invoke(app, ["check-file", str(f)])
    assert result.exit_code == 1
    assert "Missing 'cards' list" in result.stdout

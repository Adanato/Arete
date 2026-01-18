import shutil
from pathlib import Path
from typer.testing import CliRunner
from arete.interface.cli import app
from arete.application.utils.text import parse_frontmatter

runner = CliRunner()

def test_migrate_assigns_ids(tmp_path: Path):
    """Test that migrate command assigns IDs to cards."""
    # Setup
    md_file = tmp_path / "test.md"
    md_file.write_text("""---
arete: true
cards:
  - fields:
      Front: Question
      Back: Answer
---
""")
    
    # Run migrate
    result = runner.invoke(app, ["migrate", str(md_file)])
    assert result.exit_code == 0
    assert "Migrated" in result.output
    
    # Verify ID assigned
    content = md_file.read_text()
    meta, _ = parse_frontmatter(content)
    assert "cards" in meta
    assert len(meta["cards"]) == 1
    assert "id" in meta["cards"][0]
    assert meta["cards"][0]["id"].startswith("arete_")

def test_migrate_dry_run_no_changes(tmp_path: Path):
    """Test that dry-run does not modify file."""
    md_file = tmp_path / "test.md"
    original_content = """---
arete: true
cards:
  - fields:
      Front: Q
      Back: A
---
"""
    md_file.write_text(original_content)
    
    # Run dry-run
    result = runner.invoke(app, ["migrate", "--dry-run", str(md_file)])
    assert result.exit_code == 0
    assert "[DRY RUN]" in result.output
    
    # Verify NO change
    assert md_file.read_text() == original_content

def test_migrate_preserves_existing_ids(tmp_path: Path):
    """Test that existing IDs are kept."""
    md_file = tmp_path / "test.md"
    md_file.write_text("""---
arete: true
cards:
  - id: arete_EXISTING
    fields:
      Front: Q
---
""")
    
    runner.invoke(app, ["migrate", str(md_file)])
    
    content = md_file.read_text()
    meta, _ = parse_frontmatter(content)
    assert meta["cards"][0]["id"] == "arete_EXISTING"

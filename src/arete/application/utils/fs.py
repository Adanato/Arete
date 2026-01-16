import hashlib
from collections.abc import Iterable
from pathlib import Path


def iter_markdown_files(root: Path) -> Iterable[Path]:
    """
    Recursively find markdown files in a vault, skipping common hidden
    and system directories.
    """
    if root.is_file() and root.suffix.lower() == ".md":
        yield root
        return
    skip_dirs = {".git", ".obsidian", ".trash", ".venv", "node_modules"}
    for p in root.rglob("*.md"):
        parts = set(p.parts)
        if parts & skip_dirs:
            continue
        try:
            rel = p.relative_to(root)
            # Check if any part OF THE RELATIVE PATH starts with .
            if any(part.startswith(".") for part in rel.parts[:-1]):
                continue
        except ValueError:
            pass
        yield p


def file_md5(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

import hashlib
from collections.abc import Iterable
from pathlib import Path


def iter_markdown_files(root: Path) -> Iterable[Path]:
    if root.is_file() and root.suffix.lower() == ".md":
        yield root
        return
    skip_dirs = {".git", ".obsidian", ".trash", ".venv", "node_modules"}
    for p in root.rglob("*.md"):
        parts = set(p.parts)
        if parts & skip_dirs:
            continue
        # Only check for hidden directories relative to the search root?
        # Or just be smarter.
        # Use relative_to if possible
        try:
            rel = p.relative_to(root)
            # Check if any part OF THE RELATIVE PATH starts with .
            # We don't care if 'root' itself is inside a dot folder (like .pytest_cache)
            if any(part.startswith(".") for part in rel.parts[:-1]):
                continue
        except ValueError:
            # Should not happen with rglob unless symlinks mess things up
            pass
        yield p
        # print(f"DEBUG: Yielding {p}")


def file_md5(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

import sqlite3
from pathlib import Path

from arete.infrastructure.persistence.cache import ContentCache


def test_cache_init(tmp_path):
    # Should create DB file if not exists
    db_path = tmp_path / "test.db"
    ContentCache(db_path=db_path)
    assert db_path.exists()

    # Check tables
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        assert "cards" in tables
        assert "files" in tables


def test_card_hash_roundtrip(tmp_path):
    db_path = tmp_path / "test.db"
    cache = ContentCache(db_path=db_path)

    md_file = Path("/tmp/note.md")

    # Initial: should be None
    assert cache.get_hash(md_file, 1) is None

    # Set hash
    cache.set_hash(md_file, 1, "abc123hash")

    # Verify retrieval
    assert cache.get_hash(md_file, 1) == "abc123hash"

    # Verify update
    cache.set_hash(md_file, 1, "newhash")
    assert cache.get_hash(md_file, 1) == "newhash"


def test_file_meta_roundtrip(tmp_path):
    db_path = tmp_path / "test.db"
    cache = ContentCache(db_path=db_path)

    md_file = Path("/tmp/note.md")
    file_hash = "fhash1"
    meta = {"cards": [1, 2], "deck": "Default"}

    # Initial: None
    assert cache.get_file_meta(md_file, file_hash) is None

    # Set meta
    cache.set_file_meta(md_file, file_hash, meta)

    # Verify retrieval
    retrieved = cache.get_file_meta(md_file, file_hash)
    assert retrieved is not None
    assert retrieved == meta
    assert retrieved["cards"] == [1, 2]


def test_file_meta_miss_on_hash_change(tmp_path):
    db_path = tmp_path / "test.db"
    cache = ContentCache(db_path=db_path)

    md_file = Path("/tmp/note.md")
    cache.set_file_meta(md_file, "old_hash", {"v": 1})

    # Different hash should return None
    assert cache.get_file_meta(md_file, "new_hash") is None


def test_persistence(tmp_path):
    db_path = tmp_path / "persist.db"

    # Open, write, close (implicitly by letting obj die or just opening new one)
    cache1 = ContentCache(db_path=db_path)
    cache1.set_hash(Path("f1"), 1, "h1")

    # Reopen
    cache2 = ContentCache(db_path=db_path)
    assert cache2.get_hash(Path("f1"), 1) == "h1"

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any


class ContentCache:
    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            # Default to XDG-ish standard: ~/.config/o2a/cache.db
            # Fallback to old path if the cachedb already exists there?
            # No, user asked to "make everything inside .config/o2a"
            conf_dir = Path.home() / ".config/o2a"
            conf_dir.mkdir(parents=True, exist_ok=True)
            db_path = conf_dir / "cache.db"

        self.db_path = db_path
        self._lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"[cache] Using database: {self.db_path}")
        self._init_db()

    def _init_db(self):
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cards (
                    path TEXT,
                    idx INTEGER,
                    hash TEXT,
                    PRIMARY KEY (path, idx)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    path TEXT PRIMARY KEY,
                    hash TEXT,
                    meta_json TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS i_cards_path ON cards (path)")
            conn.commit()

    def get_hash(self, md_path: Path, card_index: int) -> str | None:
        # Sqlite read can be concurrent if we open a new connection per thread,
        # OR we can just lock it. For simplicity and safety with sqlite+threads,
        # let's lock. The overhead is negligible compared to apy execution.
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT hash FROM cards WHERE path = ? AND idx = ?", (str(md_path), card_index)
            )
            row = cur.fetchone()
            return row[0] if row else None

    def set_hash(self, md_path: Path, card_index: int, content_hash: str):
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cards (path, idx, hash) VALUES (?, ?, ?)",
                (str(md_path), card_index, content_hash),
            )
            conn.commit()

    def get_file_meta(self, md_path: Path, current_hash: str) -> dict[str, Any] | None:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT meta_json FROM files WHERE path = ? AND hash = ?",
                (str(md_path), current_hash),
            )
            row = cur.fetchone()
            if row:
                try:
                    res = json.loads(row[0])
                    self.logger.debug(f"[cache] meta hit for {md_path.name}")
                    return res
                except Exception:
                    pass
            self.logger.debug(f"[cache] meta miss for {md_path.name}")
            return None

    def set_file_meta(self, md_path: Path, current_hash: str, meta: dict[str, Any]):
        json_str = json.dumps(meta)
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO files (path, hash, meta_json) VALUES (?, ?, ?)",
                (str(md_path), current_hash, json_str),
            )
            conn.commit()

    def clear(self):
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cards")
            conn.execute("DELETE FROM files")
            conn.commit()

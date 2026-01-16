import asyncio
import tempfile
import time
from pathlib import Path

from arete.application.config import resolve_config
from arete.domain.interfaces import AnkiBridge
from arete.domain.models import UpdateItem, WorkItem
from arete.main import execute_sync


# Mock Bridge that always succeeds instantly
class MockBridge(AnkiBridge):
    async def sync_notes(self, work_items: list[WorkItem]) -> list[UpdateItem]:
        return [
            UpdateItem(
                source_file=wi.source_file,
                source_index=wi.source_index,
                new_nid="123",
                new_cid="456",
                ok=True,
                note=wi.note,
            )
            for wi in work_items
        ]

    async def close(self):
        pass

    async def ensure_deck(self, name):
        return True

    async def ensure_model_has_source_field(self, name):
        pass

    async def get_notes_in_deck(self, deck):
        return []

    async def delete_notes(self, nids):
        return True

    async def get_card_stats(self, nids):
        return {}

    async def get_model_names(self):
        return ["Basic"]

    async def get_deck_names(self):
        return ["Default"]

    async def delete_decks(self, names, cards_too=False):
        return

    async def get_learning_insights(self, days):
        return {}

    async def gui_browse(self, query):
        return


async def main():
    count = 10000
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        cache_db = tmp_path / "cache.db"

        print(f"Generating {count} mock notes...")
        for i in range(count):
            note_content = (
                "---\narete: true\ndeck: Default\ncards:\n"
                f"  - Front: Q{i}\n    Back: A{i}\n---\n# Note {i}"
            )
            (vault_path / f"note_{i}.md").write_text(note_content)

        config = resolve_config(
            {
                "root_input": str(vault_path),
                "backend": "ankiconnect",
                "dry_run": False,
                "workers": 10,
                "cache_db": str(cache_db),
                "verbose": 1,
            }
        )

        # Patch the factory to return our MockBridge
        import arete.infrastructure.adapters.factory as factory

        original_get = factory.get_anki_bridge

        async def mock_get(cfg):
            return MockBridge()

        factory.get_anki_bridge = mock_get

        # Instantiate cache once
        from arete.infrastructure.persistence.cache import ContentCache

        ContentCache(cache_db)

        print("\n--- Cold Sync (10k) ---")
        start = time.perf_counter()
        await execute_sync(config)
        print(f"COLD SYNC TIME: {time.perf_counter() - start:.3f}s")

        # Check if cache file exists and has size
        print(f"Cache DB size: {cache_db.stat().st_size} bytes")

        print("\n--- Hot Sync (10k) ---")
        start = time.perf_counter()

        # Ensure we are using the SAME path
        await execute_sync(config)
        print(f"HOT SYNC TIME: {time.perf_counter() - start:.3f}s")

        factory.get_anki_bridge = original_get


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import cProfile
import pstats
import tempfile
import time
from pathlib import Path

from arete.application.config import resolve_config
from arete.main import execute_sync


async def run_profiled_sync(vault_path, cache_db, count, label):
    config = resolve_config(
        {
            "root_input": str(vault_path),
            "backend": "ankiconnect",
            "dry_run": True,
            "workers": 10,
            "log_dir": str(vault_path.parent / "logs"),
            "cache_db": str(cache_db),
            "verbose": 0,
        }
    )

    print(f"\n--- {label} ({count} notes) ---")
    start = time.perf_counter()
    profiler = cProfile.Profile()
    profiler.enable()

    await execute_sync(config)

    profiler.disable()
    end = time.perf_counter()
    print(f"Total Wall Time: {end - start:.3f}s")
    stats = pstats.Stats(profiler).sort_stats("cumulative")
    stats.print_stats(20)


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

        # Profile Cold Cache
        await run_profiled_sync(vault_path, cache_db, count, "Cold Cache")

        # Profile Hot Cache
        await run_profiled_sync(vault_path, cache_db, count, "Hot Cache")


if __name__ == "__main__":
    asyncio.run(main())

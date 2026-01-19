import asyncio
import logging
from pathlib import Path

from arete.application.stats.metrics_calculator import MetricsCalculator
from arete.infrastructure.adapters.stats.direct_stats import DirectStatsRepository

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def verify_metrics():
    # User 4 path (known to have FSRS data but maybe missing history)
    # Actually let's use the default path logic from repo if possible, or hardcode one
    # We'll try to find a valid collection

    # Base Anki path
    base_path = Path("/Users/adam/Library/Application Support/Anki2")
    profile = "User 1"

    if not (base_path / "prefs21.db").exists():
        print(f"Anki base not found at {base_path}")
        return

    print(f"Verifying against: {base_path} (Profile: {profile})")

    # DirectStatsRepository likely takes just base_path, or base_path + profile
    # checking signature of DirectStatsRepository in direct_stats.py
    # class DirectStatsRepository(StatsRepository):
    #     def __init__(self, anki_base: Path, profile_name: str | None = None):
    #         self.anki_base = anki_base
    #         self.profile_name = profile_name

    repo = DirectStatsRepository(base_path)
    # If the user hasn't provided a profile arg yet, we might need to rely on it
    # picking default or manually setting it.
    # Anki 2.1.22+ uses separate collection from prefs.
    # Let's try passing just base_path.

    # We need to construct db_path manually for the sqlite check below
    repo_path = base_path / profile

    calc = MetricsCalculator()

    # Get some cards
    # We need to find note ids first.
    # Let's just query db directly to find a nid with reviews?
    # Or just use get_card_stats on a range of IDs if possible?
    # DirectStatsRepository needs note IDs (nids).

    # Let's cheat and use SQLite to find a nid with reviews
    import sqlite3

    db_path = repo_path / "collection.anki2"
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT nid FROM cards WHERE reps > 5 LIMIT 5")
    nids = [row[0] for row in cursor.fetchall()]
    conn.close()

    print(f"Testing NIDs: {nids}")

    stats = await repo.get_card_stats(nids)

    for s in stats:
        # Populate history
        s.reviews = await repo.get_review_history([s.card_id])

        # Enrich
        enriched = calc.enrich(s)

        print(f"\nCard {s.card_id} (NID {s.note_id}):")
        print(f"  Reps: {s.reps}")
        print(f"  Avg Time (agg): {s.average_time_ms} ms")
        print(f"  Interval Growth: {enriched.interval_growth}")
        print(f"  Press Fatigue: {enriched.press_fatigue}")
        print(f"  History Len: {len(s.reviews)}")
        if s.reviews:
            last = s.reviews[-1]
            print(
                f"  Last Review: ivl={last.interval}, "
                f"lastIvl={last.last_interval}, time={last.time_taken}"
            )


if __name__ == "__main__":
    asyncio.run(verify_metrics())

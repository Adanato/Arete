"""
Direct Stats Repository — Infrastructure adapter for Anki's SQLite database.

Implements StatsRepository by querying the Anki collection directly.
"""

import logging
from pathlib import Path

from arete.domain.stats.models import CardStatsAggregate, FsrsMemoryState, ReviewEntry
from arete.domain.stats.ports import StatsRepository
from arete.infrastructure.anki.repository import AnkiRepository

logger = logging.getLogger(__name__)


class DirectStatsRepository(StatsRepository):
    """
    Fetches card statistics directly from Anki's SQLite database.

    Accesses FSRS memory state via card.memory_state when available.
    """

    def __init__(self, anki_base: Path | None = None):
        self.anki_base = anki_base

    async def get_card_stats(self, nids: list[int]) -> list[CardStatsAggregate]:
        """
        Fetch comprehensive stats for cards belonging to the given note IDs.
        """
        if not nids:
            return []

        stats_list: list[CardStatsAggregate] = []

        with AnkiRepository(self.anki_base) as repo:
            if not repo.col:
                logger.warning("Could not open Anki collection")
                return []

            for nid in nids:
                try:
                    cids = repo.col.find_cards(f"nid:{nid}")

                    for cid in cids:
                        card = repo.col.get_card(cid)
                        deck = repo.col.decks.get(card.did)
                        deck_name = deck["name"] if deck else "Unknown"

                        # Extract FSRS memory state
                        fsrs_state: FsrsMemoryState | None = None
                        if hasattr(card, "memory_state") and card.memory_state:
                            ms = card.memory_state
                            difficulty = (
                                ms.difficulty / 10.0
                                if hasattr(ms, "difficulty")
                                else None
                            )
                            stability = (
                                ms.stability if hasattr(ms, "stability") else None
                            )

                            if stability is not None and difficulty is not None:
                                fsrs_state = FsrsMemoryState(
                                    stability=stability,
                                    difficulty=difficulty,
                                    retrievability=None,  # Computed by application layer
                                )

                        # Get last review time from revlog
                        last_review = self._get_last_review_time(repo, cid)

                        # Get front content
                        front = None
                        try:
                            note = repo.col.get_note(card.nid)
                            front = note.fields[0] if note.fields else None
                        except Exception:
                            pass

                        stats_list.append(
                            CardStatsAggregate(
                                card_id=card.id,
                                note_id=card.nid,
                                deck_name=deck_name,
                                lapses=card.lapses,
                                ease=card.factor,
                                interval=card.ivl,
                                due=card.due,
                                reps=card.reps,
                                fsrs=fsrs_state,
                                last_review=last_review,
                                average_time_ms=0,  # TODO: Compute from revlog
                                reviews=[],  # Populated on demand via get_review_history
                                front=front,
                            )
                        )

                except Exception as e:
                    logger.warning(f"Failed to fetch stats for nid={nid}: {e}")

        return stats_list

    async def get_review_history(self, cids: list[int]) -> list[ReviewEntry]:
        """
        Fetch review history from the revlog table.
        """
        if not cids:
            return []

        entries: list[ReviewEntry] = []

        with AnkiRepository(self.anki_base) as repo:
            if not repo.col:
                return []

            # Query revlog for all cids
            # revlog columns: id, cid, usn, ease, ivl, lastIvl, factor, time, type
            cid_str = ",".join(str(c) for c in cids)
            query = (
                f"SELECT id, cid, ease, ivl, type FROM revlog "
                f"WHERE cid IN ({cid_str}) ORDER BY id ASC"
            )

            try:
                if repo.col.db is None:
                    return []
                for row in repo.col.db.execute(query):
                    # id is the timestamp in ms
                    entries.append(
                        ReviewEntry(
                            card_id=row[1],
                            review_time=row[0] // 1000,  # Convert ms to seconds
                            rating=row[2],
                            interval=row[3],
                            review_type=row[4],
                        )
                    )
            except Exception as e:
                logger.warning(f"Failed to fetch review history: {e}")

        return entries

    def _get_last_review_time(self, repo: AnkiRepository, cid: int) -> int | None:
        """
        Get the most recent review time for a card.
        """
        try:
            if repo.col is None or repo.col.db is None:
                return None
            result = repo.col.db.scalar(
                f"SELECT MAX(id) FROM revlog WHERE cid = {cid}"
            )
            if result:
                return result // 1000  # Convert ms to seconds
        except Exception:
            pass
        return None

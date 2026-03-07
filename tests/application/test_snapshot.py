"""Tests for snapshot service: depth computation, CSV output, and orchestration."""

from unittest.mock import AsyncMock, patch

import pytest

from arete.application.snapshot import (
    CardSnapshot,
    compute_depths,
    snapshots_to_csv,
    take_snapshot,
)
from arete.domain.graph import CardNode, DependencyGraph
from arete.domain.models import AnkiCardStats


def _make_graph() -> DependencyGraph:
    """prereq1 → cardA → cardC, prereq2 → cardB → cardC, cardD (isolated)."""
    g = DependencyGraph()
    for nid in ["prereq1", "prereq2", "cardA", "cardB", "cardC", "cardD"]:
        g.add_node(CardNode(id=nid, title=nid, file_path=f"{nid}.md", line_number=1))
    g.add_requires("cardA", "prereq1")
    g.add_requires("cardB", "prereq2")
    g.add_requires("cardC", "cardA")
    g.add_requires("cardC", "cardB")
    return g


class TestComputeDepths:
    def test_roots_have_depth_zero(self):
        graph = _make_graph()
        depths = compute_depths(graph)
        assert depths["prereq1"] == 0
        assert depths["prereq2"] == 0
        assert depths["cardD"] == 0  # isolated = root

    def test_direct_dependents_have_depth_one(self):
        graph = _make_graph()
        depths = compute_depths(graph)
        assert depths["cardA"] == 1
        assert depths["cardB"] == 1

    def test_transitive_dependent_has_max_depth(self):
        graph = _make_graph()
        depths = compute_depths(graph)
        assert depths["cardC"] == 2

    def test_empty_graph(self):
        graph = DependencyGraph()
        depths = compute_depths(graph)
        assert depths == {}

    def test_linear_chain(self):
        g = DependencyGraph()
        for nid in ["a", "b", "c", "d"]:
            g.add_node(CardNode(id=nid, title=nid, file_path=f"{nid}.md", line_number=1))
        g.add_requires("b", "a")
        g.add_requires("c", "b")
        g.add_requires("d", "c")

        depths = compute_depths(g)
        assert depths == {"a": 0, "b": 1, "c": 2, "d": 3}


class TestSnapshotsToCsv:
    def test_header_and_rows(self):
        snapshots = [
            CardSnapshot(
                arete_id="arete_001",
                depth=0,
                title="Root Card",
                file="root.md",
                stability=None,
                difficulty=0.3,
                retrievability=None,
                reps=10,
                lapses=2,
                interval=30,
                again_rate=0.2,
            ),
        ]
        csv_text = snapshots_to_csv(snapshots)
        lines = csv_text.strip().split("\n")
        assert len(lines) == 2  # header + 1 row
        assert "arete_id" in lines[0]
        assert "arete_001" in lines[1]
        assert "0.2000" in lines[1]

    def test_empty_snapshots(self):
        csv_text = snapshots_to_csv([])
        lines = csv_text.strip().split("\n")
        assert len(lines) == 1  # header only

    def test_none_again_rate(self):
        snapshots = [
            CardSnapshot(
                arete_id="arete_002",
                depth=1,
                title="New Card",
                file="new.md",
                stability=None,
                difficulty=None,
                retrievability=None,
                reps=0,
                lapses=0,
                interval=0,
                again_rate=None,
            ),
        ]
        csv_text = snapshots_to_csv(snapshots)
        # Last field should be empty, not "None"
        assert "None" not in csv_text


class TestTakeSnapshot:
    @pytest.mark.asyncio
    @patch("arete.application.snapshot.build_graph")
    async def test_joins_depth_with_stats(self, mock_build_graph, tmp_path):
        graph = _make_graph()
        mock_build_graph.return_value = graph

        mock_anki = AsyncMock()
        mock_anki.find_all_arete_nids.return_value = [100, 200, 300]
        mock_anki.map_nids_to_arete_ids.return_value = ["prereq1", "cardA", "cardC"]
        mock_anki.get_card_stats.return_value = [
            AnkiCardStats(
                card_id=1001,
                note_id=100,
                lapses=0,
                ease=2500,
                difficulty=0.3,
                deck_name="Test",
                interval=30,
                due=0,
                reps=10,
            ),
            AnkiCardStats(
                card_id=1002,
                note_id=200,
                lapses=1,
                ease=2500,
                difficulty=0.5,
                deck_name="Test",
                interval=15,
                due=0,
                reps=8,
            ),
            AnkiCardStats(
                card_id=1003,
                note_id=300,
                lapses=3,
                ease=2500,
                difficulty=0.7,
                deck_name="Test",
                interval=7,
                due=0,
                reps=12,
            ),
        ]

        result = await take_snapshot(mock_anki, tmp_path)

        assert len(result) == 3
        by_id = {s.arete_id: s for s in result}

        assert by_id["prereq1"].depth == 0
        assert by_id["cardA"].depth == 1
        assert by_id["cardC"].depth == 2

        assert by_id["prereq1"].again_rate == 0.0
        assert by_id["cardA"].again_rate == pytest.approx(1 / 8)
        assert by_id["cardC"].again_rate == pytest.approx(3 / 12)

    @pytest.mark.asyncio
    @patch("arete.application.snapshot.build_graph")
    async def test_empty_when_no_anki_notes(self, mock_build_graph, tmp_path):
        mock_build_graph.return_value = _make_graph()
        mock_anki = AsyncMock()
        mock_anki.find_all_arete_nids.return_value = []

        result = await take_snapshot(mock_anki, tmp_path)
        assert result == []

    @pytest.mark.asyncio
    @patch("arete.application.snapshot.build_graph")
    async def test_skips_cards_not_in_graph(self, mock_build_graph, tmp_path):
        graph = _make_graph()
        mock_build_graph.return_value = graph

        mock_anki = AsyncMock()
        mock_anki.find_all_arete_nids.return_value = [100, 999]
        mock_anki.map_nids_to_arete_ids.return_value = ["prereq1", "unknown_card"]
        mock_anki.get_card_stats.return_value = [
            AnkiCardStats(
                card_id=1001,
                note_id=100,
                lapses=0,
                ease=2500,
                difficulty=0.3,
                deck_name="Test",
                interval=30,
                due=0,
                reps=10,
            ),
            AnkiCardStats(
                card_id=9999,
                note_id=999,
                lapses=0,
                ease=2500,
                difficulty=0.1,
                deck_name="Test",
                interval=1,
                due=0,
                reps=1,
            ),
        ]

        result = await take_snapshot(mock_anki, tmp_path)
        assert len(result) == 1
        assert result[0].arete_id == "prereq1"

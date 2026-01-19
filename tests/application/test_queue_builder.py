from pathlib import Path
from unittest.mock import patch

import pytest

from arete.application.queue_builder import build_simple_queue
from arete.domain.graph import CardNode, DependencyGraph


@pytest.fixture
def mock_graph_deps():
    """Creates a dependency graph:
    A -> B (A requires B)
    B -> C (B requires C)
    D (independent)
    E <-> F (Cycle)
    """
    graph = DependencyGraph()

    # Nodes
    graph.nodes["A"] = CardNode(id="A", file_path="a.md", title="A", line_number=1)
    graph.nodes["B"] = CardNode(id="B", file_path="b.md", title="B", line_number=1)
    graph.nodes["C"] = CardNode(id="C", file_path="c.md", title="C", line_number=1)
    graph.nodes["D"] = CardNode(id="D", file_path="d.md", title="D", line_number=1)
    graph.nodes["E"] = CardNode(id="E", file_path="e.md", title="E", line_number=1)
    graph.nodes["F"] = CardNode(id="F", file_path="f.md", title="F", line_number=1)

    # Dependencies (requires)
    graph.add_requires("A", "B")
    graph.add_requires("B", "C")
    graph.add_requires("E", "F")
    graph.add_requires("F", "E")

    return graph


@patch("arete.application.graph_resolver.build_graph")
def test_build_simple_queue_mvp(mock_build_graph, mock_graph_deps):
    """Test basic queue building with prerequisites."""
    mock_build_graph.return_value = mock_graph_deps

    # Case 1: Just A is due. Must fetch B and C.
    # Expected order: C, B, A (topolocial)
    # Prereqs: C, B
    # Main: A
    res = build_simple_queue(Path("."), due_card_ids=["A"], depth=5)

    assert "C" in res.prereq_queue
    assert "B" in res.prereq_queue
    assert res.main_queue == ["A"]

    # Ensure topo order
    assert res.prereq_queue.index("C") < res.prereq_queue.index("B")


@patch("arete.application.graph_resolver.build_graph")
def test_build_simple_queue_depth(mock_build_graph, mock_graph_deps):
    """Test recursion depth limit."""
    mock_build_graph.return_value = mock_graph_deps

    # Case: A is due, depth=1. Should fetch B, but NOT C (since B->C is depth 2 from A)
    res = build_simple_queue(Path("."), due_card_ids=["A"], depth=1)

    assert "B" in res.prereq_queue
    assert "C" not in res.prereq_queue
    assert res.main_queue == ["A"]


@patch("arete.application.graph_resolver.build_graph")
def test_build_simple_queue_independent(mock_build_graph, mock_graph_deps):
    """Test independent cards have no prereqs."""
    mock_build_graph.return_value = mock_graph_deps

    res = build_simple_queue(Path("."), due_card_ids=["D"])

    assert res.prereq_queue == []
    assert res.main_queue == ["D"]


@patch("arete.application.graph_resolver.build_graph")
def test_build_simple_queue_cycle(mock_build_graph, mock_graph_deps):
    """Test cycle detection doesn't crash queue builder."""
    mock_build_graph.return_value = mock_graph_deps

    # Case: E is due (E<->F)
    res = build_simple_queue(Path("."), due_card_ids=["E"])

    # In a cycle, order is undefined but should return both
    assert "F" in res.prereq_queue
    assert "E" in res.main_queue

    # Should report cycle
    assert len(res.cycles) > 0


@patch("arete.application.graph_resolver.build_graph")
def test_build_simple_queue_max_cards(mock_build_graph, mock_graph_deps):
    """Test constraints on queue size."""
    mock_build_graph.return_value = mock_graph_deps

    # Should contain C, B, A (3 cards). Max 2.
    # Logic prioritizes keeping due cards. So we trim prereqs.
    # A is due (size 1). Available space for prereqs = 1.
    # Prereqs are C, B. One will be dropped.

    res = build_simple_queue(Path("."), due_card_ids=["A"], max_cards=2)

    assert len(res.main_queue) == 1
    assert len(res.prereq_queue) == 1
    assert len(res.prereq_queue) + len(res.main_queue) <= 2

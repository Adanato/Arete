"""Tests for graph resolver and queue builder."""

import tempfile
from pathlib import Path

import pytest

from arete.application.graph_resolver import (
    build_graph,
    detect_cycles,
    get_local_graph,
    topological_sort,
)
from arete.application.queue_builder import (
    QueueBuildResult,
    WeakPrereqCriteria,
    build_dependency_queue,
)
from arete.domain.graph import CardNode, DependencyGraph


class TestDependencyGraph:
    """Tests for DependencyGraph domain model."""

    def test_add_node(self):
        graph = DependencyGraph()
        node = CardNode(id="a1", title="Card A", file_path="/test.md", line_number=1)
        graph.add_node(node)

        assert "a1" in graph.nodes
        assert graph.nodes["a1"].title == "Card A"

    def test_add_requires(self):
        graph = DependencyGraph()
        graph.add_node(CardNode("a1", "A", "/a.md", 1))
        graph.add_node(CardNode("a2", "B", "/b.md", 1))
        graph.add_requires("a1", "a2")  # a1 requires a2

        assert graph.get_prerequisites("a1") == ["a2"]
        assert graph.get_dependents("a2") == ["a1"]

    def test_add_related(self):
        graph = DependencyGraph()
        graph.add_node(CardNode("a1", "A", "/a.md", 1))
        graph.add_node(CardNode("a2", "B", "/b.md", 1))
        graph.add_related("a1", "a2")

        assert graph.get_related("a1") == ["a2"]


class TestBuildGraph:
    """Tests for building graph from vault files."""

    def test_build_graph_from_yaml(self, tmp_path: Path):
        """Test parsing cards with deps from frontmatter."""
        md_content = """---
arete: true
deck: Test
cards:
  - id: arete_001
    model: Basic
    fields:
      Front: "Question 1"
      Back: "Answer 1"
    deps:
      requires: [arete_002]
      related: [arete_003]
  - id: arete_002
    model: Basic
    fields:
      Front: "Question 2"
      Back: "Answer 2"
  - id: arete_003
    model: Basic
    fields:
      Front: "Question 3"
      Back: "Answer 3"
---

# Test Note
"""
        (tmp_path / "test.md").write_text(md_content)

        graph = build_graph(tmp_path)

        assert "arete_001" in graph.nodes
        assert "arete_002" in graph.nodes
        assert "arete_003" in graph.nodes
        assert graph.get_prerequisites("arete_001") == ["arete_002"]
        assert graph.get_related("arete_001") == ["arete_003"]

    def test_build_graph_skips_cards_without_id(self, tmp_path: Path):
        """Test that cards without id field are skipped."""
        md_content = """---
arete: true
deck: Test
cards:
  - model: Basic
    fields:
      Front: "No ID"
      Back: "Skipped"
---
"""
        (tmp_path / "test.md").write_text(md_content)

        graph = build_graph(tmp_path)

        assert len(graph.nodes) == 0


class TestLocalGraph:
    """Tests for local graph queries."""

    def test_get_local_graph(self):
        """Test local subgraph extraction."""
        graph = DependencyGraph()
        graph.add_node(CardNode("a", "A", "/a.md", 1))
        graph.add_node(CardNode("b", "B", "/b.md", 1))
        graph.add_node(CardNode("c", "C", "/c.md", 1))
        graph.add_requires("a", "b")  # a requires b
        graph.add_requires("b", "c")  # b requires c

        result = get_local_graph(graph, "a", depth=2)

        assert result is not None
        assert result.center.id == "a"
        assert len(result.prerequisites) == 2  # b and c
        prereq_ids = {p.id for p in result.prerequisites}
        assert "b" in prereq_ids
        assert "c" in prereq_ids

    def test_get_local_graph_depth_limit(self):
        """Test that depth limit is respected."""
        graph = DependencyGraph()
        graph.add_node(CardNode("a", "A", "/a.md", 1))
        graph.add_node(CardNode("b", "B", "/b.md", 1))
        graph.add_node(CardNode("c", "C", "/c.md", 1))
        graph.add_requires("a", "b")
        graph.add_requires("b", "c")

        result = get_local_graph(graph, "a", depth=1)

        assert result is not None
        assert len(result.prerequisites) == 1  # Only b, not c
        assert result.prerequisites[0].id == "b"

    def test_get_local_graph_not_found(self):
        """Test handling of non-existent card."""
        graph = DependencyGraph()
        result = get_local_graph(graph, "nonexistent")
        assert result is None


class TestCycleDetection:
    """Tests for cycle detection."""

    def test_detect_no_cycles(self):
        """Test graph with no cycles."""
        graph = DependencyGraph()
        graph.add_node(CardNode("a", "A", "/a.md", 1))
        graph.add_node(CardNode("b", "B", "/b.md", 1))
        graph.add_requires("a", "b")

        cycles = detect_cycles(graph)
        assert len(cycles) == 0

    def test_detect_simple_cycle(self):
        """Test detection of a simple cycle."""
        graph = DependencyGraph()
        graph.add_node(CardNode("a", "A", "/a.md", 1))
        graph.add_node(CardNode("b", "B", "/b.md", 1))
        graph.add_requires("a", "b")
        graph.add_requires("b", "a")

        cycles = detect_cycles(graph)
        assert len(cycles) > 0


class TestTopologicalSort:
    """Tests for topological sorting."""

    def test_topological_sort_basic(self):
        """Test basic topological sort."""
        graph = DependencyGraph()
        graph.add_node(CardNode("a", "A", "/a.md", 1))
        graph.add_node(CardNode("b", "B", "/b.md", 1))
        graph.add_node(CardNode("c", "C", "/c.md", 1))
        graph.add_requires("a", "b")  # a requires b
        graph.add_requires("b", "c")  # b requires c

        result = topological_sort(graph, ["a", "b", "c"])

        # c should come before b, b before a
        assert result.index("c") < result.index("b")
        assert result.index("b") < result.index("a")

    def test_topological_sort_subset(self):
        """Test sorting a subset of cards."""
        graph = DependencyGraph()
        graph.add_node(CardNode("a", "A", "/a.md", 1))
        graph.add_node(CardNode("b", "B", "/b.md", 1))
        graph.add_node(CardNode("c", "C", "/c.md", 1))
        graph.add_requires("a", "b")
        graph.add_requires("b", "c")

        result = topological_sort(graph, ["a", "b"])  # Exclude c

        assert "c" not in result
        assert result.index("b") < result.index("a")


class TestQueueBuilder:
    """Tests for dependency-aware queue building."""

    def test_build_dependency_queue(self, tmp_path: Path):
        """Test full queue building flow."""
        md_content = """---
arete: true
deck: Test
cards:
  - id: arete_main
    model: Basic
    fields:
      Front: "Main card"
      Back: "Due today"
    deps:
      requires: [arete_prereq]
  - id: arete_prereq
    model: Basic
    fields:
      Front: "Prereq card"
      Back: "Should study first"
---
"""
        (tmp_path / "test.md").write_text(md_content)

        result = build_dependency_queue(
            vault_root=tmp_path,
            due_card_ids=["arete_main"],
            depth=2,
        )

        assert "arete_prereq" in result.prereq_queue
        assert "arete_main" in result.main_queue

    def test_include_related_not_implemented(self, tmp_path: Path):
        """Test that include_related raises NotImplementedError."""
        (tmp_path / "test.md").write_text("---\narete: true\ncards: []\n---")

        with pytest.raises(NotImplementedError, match="Related card boost"):
            build_dependency_queue(
                vault_root=tmp_path,
                due_card_ids=[],
                include_related=True,
            )

    def test_weak_prereq_filtering(self, tmp_path: Path):
        """Test filtering based on weak criteria."""
        md_content = """---
arete: true
deck: Test
cards:
  - id: main
    model: Basic
    fields:
      Front: "Main"
    deps:
      requires: [weak, strong]
  - id: weak
    model: Basic
    fields:
      Front: "Weak prereq"
  - id: strong
    model: Basic
    fields:
      Front: "Strong prereq"
---
"""
        (tmp_path / "test.md").write_text(md_content)

        card_stats = {
            "weak": {"stability": 5.0, "lapses": 3},
            "strong": {"stability": 100.0, "lapses": 0},
        }

        result = build_dependency_queue(
            vault_root=tmp_path,
            due_card_ids=["main"],
            weak_criteria=WeakPrereqCriteria(min_stability=50.0),
            card_stats=card_stats,
        )

        assert "weak" in result.prereq_queue
        assert "strong" in result.skipped_strong

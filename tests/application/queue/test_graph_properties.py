"""Property-based tests for dependency graph and topological sort."""

from hypothesis import given, settings
from hypothesis import strategies as st

from arete.application.queue.graph_resolver import detect_cycles, topological_sort
from arete.domain.graph import CardNode, DependencyGraph


def _make_id(i: int) -> str:
    return f"arete_TEST{i:022d}"


def _make_graph(n: int, edges: list[tuple[str, str]]) -> tuple[DependencyGraph, list[str]]:
    """Build a DependencyGraph with n nodes and the given requires edges."""
    ids = [_make_id(i) for i in range(n)]
    graph = DependencyGraph()
    for cid in ids:
        graph.add_node(CardNode(id=cid, title=cid, file_path="test.md", line_number=1))
    for from_id, to_id in edges:
        graph.add_requires(from_id, to_id)  # from_id requires to_id
    return graph, ids


@st.composite
def dag_strategy(draw):
    """Generate a DAG: edges only go from higher index to lower (guarantees acyclic)."""
    n = draw(st.integers(min_value=1, max_value=20))
    ids = [_make_id(i) for i in range(n)]
    edges = []
    for i in range(n):
        for j in range(i):
            if draw(st.booleans()):
                edges.append((ids[i], ids[j]))  # i requires j
    return ids, edges


@given(dag=dag_strategy())
@settings(max_examples=100)
def test_topo_sort_preserves_all_ids(dag):
    """set(topo_sort(graph, ids)) == set(valid_ids) -- no cards lost or duplicated."""
    ids, edges = dag
    graph, _ = _make_graph(len(ids), edges)
    result = topological_sort(graph, ids)
    assert set(result) == set(ids)
    assert len(result) == len(ids)


@given(dag=dag_strategy())
@settings(max_examples=100)
def test_topo_sort_respects_edges(dag):
    """For every edge A->B (A requires B), B appears before A in result."""
    ids, edges = dag
    graph, _ = _make_graph(len(ids), edges)
    result = topological_sort(graph, ids)
    pos = {cid: i for i, cid in enumerate(result)}
    for from_id, to_id in edges:
        # from_id requires to_id, so to_id (prerequisite) must come first
        assert pos[to_id] < pos[from_id], (
            f"{to_id} (prereq) should appear before {from_id} (dependent)"
        )


def test_topo_sort_empty_input():
    graph, _ = _make_graph(0, [])
    assert topological_sort(graph, []) == []


def test_topo_sort_single_node():
    graph, ids = _make_graph(1, [])
    result = topological_sort(graph, ids)
    assert result == ids


def test_topo_sort_unknown_ids_filtered():
    """IDs not in graph are excluded from result."""
    graph, ids = _make_graph(2, [])
    result = topological_sort(graph, ids + ["arete_UNKNOWN00000000000000"])
    assert set(result) == set(ids)


def test_graph_add_requires_edge_direction():
    """add_requires(A, B) -> B is predecessor of A."""
    graph, ids = _make_graph(2, [])
    a, b = ids
    graph.add_requires(a, b)  # A requires B
    assert b in graph.get_prerequisites(a)
    assert a in graph.get_dependents(b)


def test_graph_prerequisites_consistent():
    """get_prerequisites(A) matches predecessors(A) in nx graph."""
    graph, ids = _make_graph(3, [])
    a, b, c = ids
    graph.add_requires(a, b)
    graph.add_requires(a, c)
    prereqs = set(graph.get_prerequisites(a))
    nx_preds = set(graph._graph.predecessors(a))
    assert prereqs == nx_preds


def test_detect_cycles_on_dag():
    """DAG -> no cycles detected."""
    ids = [_make_id(i) for i in range(5)]
    edges = [(ids[1], ids[0]), (ids[2], ids[1]), (ids[3], ids[2]), (ids[4], ids[3])]
    graph, _ = _make_graph(5, edges)
    cycles = detect_cycles(graph)
    assert cycles == []


def test_detect_cycles_on_cyclic():
    """A->B->A -> cycle detected containing both."""
    graph, ids = _make_graph(2, [])
    a, b = ids
    graph.add_requires(a, b)
    graph.add_requires(b, a)
    cycles = detect_cycles(graph)
    assert len(cycles) >= 1
    cycle_members = set()
    for cycle in cycles:
        cycle_members.update(cycle)
    assert a in cycle_members
    assert b in cycle_members


def test_detect_cycles_three_node_cycle():
    """A->B->C->A forms a cycle."""
    graph, ids = _make_graph(3, [])
    a, b, c = ids
    graph.add_requires(a, b)
    graph.add_requires(b, c)
    graph.add_requires(c, a)
    cycles = detect_cycles(graph)
    assert len(cycles) >= 1
    cycle_members = set()
    for cycle in cycles:
        cycle_members.update(cycle)
    assert {a, b, c} <= cycle_members

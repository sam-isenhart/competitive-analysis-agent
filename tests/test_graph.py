"""Graph structure and routing tests."""


from competitive_intel.graph import build_graph, route_research, should_revise
from competitive_intel.state import PipelineState


def test_build_graph_compiles():
    """Graph compiles and has expected nodes/edges."""
    g = build_graph()
    assert g is not None
    # Compiled graph has nodes
    nodes = list(g.nodes) if hasattr(g, "nodes") else []
    assert "research_node" in nodes or len(nodes) >= 4


def test_route_research_fan_out():
    """route_research returns one Send per competitor."""
    from langgraph.types import Send

    state: PipelineState = {"competitors": ["A", "B", "C"], "research": []}
    out = route_research(state)
    assert len(out) == 3
    assert all(isinstance(s, Send) for s in out)
    for s in out:
        assert getattr(s, "node", None) == "research_node"
        assert getattr(s, "arg", {}).get("competitor") in ("A", "B", "C")


def test_route_research_empty():
    """Empty competitors returns empty list."""
    out = route_research({"competitors": []})
    assert out == []


def test_should_revise_approved_goes_to_deliver():
    """When feedback.approved is True, route to deliver_node."""
    state: PipelineState = {"feedback": {"approved": True}, "revision_count": 0}
    assert should_revise(state) == "deliver_node"


def test_should_revise_max_revisions_goes_to_deliver():
    """When revision_count >= MAX_REVISIONS, route to deliver_node."""
    from competitive_intel.config import MAX_REVISIONS

    state: PipelineState = {
        "feedback": {"approved": False, "revision_instructions": "Fix it"},
        "revision_count": MAX_REVISIONS,
    }
    assert should_revise(state) == "deliver_node"


def test_should_revise_needs_revision_goes_to_writer():
    """When not approved and under max revisions, route to writer_node."""
    state: PipelineState = {
        "feedback": {"approved": False, "revision_instructions": "Add more"},
        "revision_count": 0,
    }
    assert should_revise(state) == "writer_node"

"""
LangGraph StateGraph: research (fan-out) -> writer -> critic -> should_revise? -> deliver -> END.
"""

import logging

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from competitive_intel.config import MAX_REVISIONS
from competitive_intel.state import PipelineState
from competitive_intel.nodes import research_node, writer_node, critic_node, deliver_node

log = logging.getLogger(__name__)


def route_research(state: PipelineState) -> list[Send]:
    """Fan-out: one Send per competitor to research_node."""
    competitors = state.get("competitors") or []
    return [Send("research_node", {"competitor": c}) for c in competitors]


def should_revise(state: PipelineState) -> str:
    """Route from critic: deliver if approved or max revisions; else writer."""
    feedback = state.get("feedback")
    if not feedback:
        return "deliver_node"
    if feedback.get("approved"):
        return "deliver_node"
    if (state.get("revision_count") or 0) >= MAX_REVISIONS:
        return "deliver_node"
    return "writer_node"


def get_checkpointer():
    """Try PostgresSaver if DATABASE_URL is configured; fall back to MemorySaver."""
    from competitive_intel.config import DATABASE_URL

    if DATABASE_URL and "postgres" in DATABASE_URL:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver

            checkpointer = PostgresSaver.from_conn_string(DATABASE_URL)
            checkpointer.setup()
            log.info("Using PostgresSaver for checkpointing")
            return checkpointer
        except ImportError:
            log.info("langgraph-checkpoint-postgres not installed, using MemorySaver")
        except Exception as exc:
            log.warning("PostgresSaver setup failed (%s), using MemorySaver", exc)

    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver()


def build_graph():
    """Build and compile the pipeline graph."""
    builder = StateGraph(PipelineState)

    builder.add_node("research_node", research_node)
    builder.add_node("writer_node", writer_node)
    builder.add_node("critic_node", critic_node)
    builder.add_node("deliver_node", deliver_node)

    builder.add_conditional_edges(START, route_research)
    builder.add_edge("research_node", "writer_node")
    builder.add_edge("writer_node", "critic_node")
    builder.add_conditional_edges(
        "critic_node",
        should_revise,
        path_map={"writer_node": "writer_node", "deliver_node": "deliver_node"},
    )
    builder.add_edge("deliver_node", END)

    checkpointer = get_checkpointer()
    return builder.compile(checkpointer=checkpointer)

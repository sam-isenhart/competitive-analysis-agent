"""Unit tests for pipeline nodes (mocked LLM calls)."""

from unittest.mock import MagicMock

from competitive_intel.state import PipelineState
from competitive_intel.nodes.critic import CriticFeedbackSchema, critic_node
from competitive_intel.nodes.deliver import deliver_node
from competitive_intel.nodes.writer import writer_node
from competitive_intel.nodes.research import research_node


def test_critic_node_empty_brief():
    """Critic with no brief returns not approved (no LLM call needed)."""
    state: PipelineState = {"brief": "", "research": []}
    out = critic_node(state)
    assert out["feedback"]["approved"] is False
    issues = out["feedback"].get("issues", [])
    assert any("brief" in str(i).lower() for i in issues)


def test_critic_node_returns_feedback(mock_chat_anthropic):
    """Critic node returns a feedback dict with required keys."""
    _, _, structured = mock_chat_anthropic
    structured.invoke.return_value = CriticFeedbackSchema(
        approved=True,
        overall_score=8,
        strengths=["Good structure"],
        issues=[],
        revision_instructions="",
    )

    state: PipelineState = {
        "brief": "# Test Brief\n\nThis is a short test.",
        "research": [{"company": "TestCo", "summary": "A test company."}],
    }
    out = critic_node(state)
    assert "feedback" in out
    fb = out["feedback"]
    assert fb["approved"] is True
    assert fb["overall_score"] == 8
    assert "revision_instructions" in fb


def test_deliver_node_writes_metadata(tmp_path, monkeypatch):
    """Deliver node returns metadata with expected keys."""
    monkeypatch.setattr("competitive_intel.nodes.deliver.FINAL_DIR", tmp_path)
    monkeypatch.setattr("competitive_intel.nodes.deliver.NOTIFY_EMAIL", "")
    monkeypatch.setattr("competitive_intel.nodes.deliver.NOTION_API_KEY", "")
    monkeypatch.setattr("competitive_intel.nodes.deliver.NOTION_DATABASE_ID", "")

    state: PipelineState = {
        "brief": "# Brief\n\nContent.",
        "feedback": {"approved": True, "overall_score": 8},
        "research": [{"company": "TestCo"}],
    }
    out = deliver_node(state)
    assert "metadata" in out
    meta = out["metadata"]
    assert meta["date"]
    assert meta["quality_score"] == 8
    assert meta["approved"] is True
    assert meta["brief_length_chars"] > 0
    assert "brief_path" in meta


def test_writer_node_returns_brief(mock_chat_anthropic, tmp_path, monkeypatch):
    """Writer node with research returns non-empty brief."""
    monkeypatch.setattr("competitive_intel.nodes.writer.DRAFTS_DIR", tmp_path)

    state: PipelineState = {
        "research": [
            {
                "company": "TestCo",
                "summary": "Test summary.",
                "recent_news": [],
                "product_updates": [],
                "strategic_moves": [],
                "strengths": [],
                "weaknesses": [],
                "sentiment": "neutral",
                "confidence": "high",
            }
        ],
        "feedback": None,
        "revision_count": 0,
    }
    out = writer_node(state)
    assert "brief" in out
    assert out["brief"]  # non-empty
    assert out["revision_count"] == 0


def test_writer_node_increments_revision_on_feedback(mock_chat_anthropic, tmp_path, monkeypatch):
    """Writer increments revision_count when given feedback with instructions."""
    monkeypatch.setattr("competitive_intel.nodes.writer.DRAFTS_DIR", tmp_path)

    state: PipelineState = {
        "research": [{"company": "TestCo", "summary": "Summary."}],
        "feedback": {
            "approved": False,
            "overall_score": 5,
            "revision_instructions": "Add more detail.",
        },
        "revision_count": 1,
    }
    out = writer_node(state)
    assert out["revision_count"] == 2


def test_research_node_empty_competitor():
    """Research node with empty competitor returns empty list."""
    state: PipelineState = {"competitor": ""}
    out = research_node(state)
    assert out == {"research": []}


def test_perplexity_tool_no_api_key(monkeypatch):
    """perplexity_search_tool returns a graceful error dict when API key is not set."""
    monkeypatch.setattr("competitive_intel.tools.perplexity_search.PERPLEXITY_API_KEY", "")
    from competitive_intel.tools.perplexity_search import perplexity_search_tool

    result = perplexity_search_tool.invoke({"query": "test query"})
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["headline"] == "N/A"
    assert "PERPLEXITY_API_KEY" in result[0]["summary"]


def test_config_sanitizer():
    """_sanitize_competitor strips path traversal and dangerous chars."""
    from competitive_intel.config import _sanitize_competitor

    assert _sanitize_competitor("../etc/passwd") == "etcpasswd"
    assert _sanitize_competitor("Company\x00Name") == "CompanyName"
    assert _sanitize_competitor("Good Corp") == "Good Corp"
    assert len(_sanitize_competitor("A" * 200)) == 100


def test_research_node_runs_tool_loop(mock_chat_anthropic, tmp_path, monkeypatch):
    """Research node produces a dossier after tool use loop."""
    from competitive_intel.nodes.research import ResearchDossierSchema
    from unittest.mock import MagicMock as MM

    monkeypatch.setattr("competitive_intel.nodes.research.RESEARCH_DIR", tmp_path)
    # Ensure at least one tool is registered even without real API keys
    mock_tool = MM()
    mock_tool.invoke.return_value = [{"headline": "news", "url": "https://x.com", "summary": ""}]
    monkeypatch.setattr("competitive_intel.nodes.research.TOOL_MAP", {"perplexity_search_tool": mock_tool})

    _, instance, structured = mock_chat_anthropic
    # First invoke: no tool calls (skip loop)
    first_response = MagicMock()
    first_response.tool_calls = []
    first_response.content = "Research gathered."
    instance.invoke.return_value = first_response

    # Structured output returns a dossier
    structured.invoke.return_value = ResearchDossierSchema(
        company="TestCo",
        date="2026-02-21",
        summary="Test summary from tools.",
        strengths=["Good product"],
        weaknesses=["Small market"],
        sentiment="positive",
        confidence="high",
        sources=["https://example.com"],
    )

    state: PipelineState = {"competitor": "TestCo"}
    out = research_node(state)
    assert len(out["research"]) == 1
    dossier = out["research"][0]
    assert dossier["company"] == "TestCo"
    assert dossier["confidence"] == "high"

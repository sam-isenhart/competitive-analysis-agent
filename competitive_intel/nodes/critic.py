"""
Critic node — reviews the brief and returns structured CriticFeedback (Sonnet).
"""

import json
import logging
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from anthropic import InternalServerError, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from competitive_intel.callbacks import UsageTracker
from competitive_intel.config import ANTHROPIC_API_KEY, MODEL_FAST
from competitive_intel.state import CriticFeedback, PipelineState

log = logging.getLogger(__name__)

# ── Module-level LLM singleton ────────────────────────────────────────────────
_LLM = ChatAnthropic(
    model=MODEL_FAST,
    api_key=ANTHROPIC_API_KEY,
    max_tokens=1024,
)


class CriticFeedbackSchema(BaseModel):
    approved: bool = False
    overall_score: int = Field(ge=1, le=10)
    strengths: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    revision_instructions: str = ""


SYSTEM_PROMPT = """\
You are a senior editor at a competitive intelligence firm. Your job is to
review briefs written by junior analysts and either approve them or request
specific revisions.

Evaluate the brief on these criteria:
1. **Accuracy** — Are claims specific and well-supported by the research data?
2. **Completeness** — Does it cover all competitors in the research?
3. **Actionability** — Are the recommendations concrete and useful?
4. **Clarity** — Is it well-organized and concise?
5. **Professionalism** — Is the tone appropriate for executives?

Be constructive but rigorous. Only approve briefs scoring 7+ overall.
Return the structured feedback (approved, overall_score, strengths, issues, revision_instructions).
"""


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=5, max=60),
    retry=retry_if_exception_type((InternalServerError, RateLimitError, Exception)),
    reraise=True,
)
def _invoke_structured(llm: Any, messages: list) -> Any:
    return llm.invoke(messages, config={"callbacks": [UsageTracker()]})


def critic_node(state: PipelineState) -> dict[str, Any]:
    """Review the brief against research; return feedback dict."""
    brief = state.get("brief") or ""
    research = state.get("research") or []

    if not brief:
        return {
            "feedback": {
                "approved": False,
                "overall_score": 0,
                "strengths": [],
                "issues": ["No brief to review."],
                "revision_instructions": "",
            }
        }

    research_summary = json.dumps(
        [{"company": r.get("company"), "summary": r.get("summary")} for r in research],
        indent=2,
    )
    user_content = (
        f"## Source Research (summaries)\n{research_summary}\n\n"
        f"## Brief to Review\n{brief}"
    )

    structured_llm = _LLM.with_structured_output(CriticFeedbackSchema)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]
    try:
        out = _invoke_structured(structured_llm, messages)
        feedback: CriticFeedback = {
            "approved": out.approved,
            "overall_score": out.overall_score,
            "strengths": out.strengths or [],
            "issues": out.issues or [],
            "revision_instructions": out.revision_instructions or "",
        }
        log.info(
            "Critic score: %d/10 — %s",
            feedback["overall_score"],
            "APPROVED" if feedback["approved"] else "REVISION NEEDED",
        )
    except Exception as exc:
        log.warning("Critic structured output failed: %s", exc)
        feedback = {
            "approved": False,
            "overall_score": 0,
            "strengths": [],
            "issues": ["Could not parse critic response"],
            "revision_instructions": "Please try again — critic output was malformed.",
        }

    return {"feedback": feedback}

"""
LangGraph state schema and reducers.

Fan-in for parallel research uses operator.add on the research list.
"""

import operator
from typing import Annotated, TypedDict


class ResearchDossier(TypedDict, total=False):
    company: str
    date: str
    summary: str
    recent_news: list[str]
    product_updates: list[str]
    strategic_moves: list[str]
    strengths: list[str]
    weaknesses: list[str]
    sentiment: str
    confidence: str
    sources: list[str]  # URLs used during research


class CriticFeedback(TypedDict, total=False):
    approved: bool
    overall_score: int
    strengths: list[str]
    issues: list[str]
    revision_instructions: str


class PipelineState(TypedDict, total=False):
    competitors: list[str]
    competitor: str  # Set by Send payload for research_node
    research: Annotated[list, operator.add]  # fan-in
    brief: str
    feedback: CriticFeedback | None
    revision_count: int
    final_brief: str
    metadata: dict

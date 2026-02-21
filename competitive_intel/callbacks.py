"""
LangChain callback handler for token usage tracking.

Import and pass UsageTracker() in callbacks= on any LLM invoke call
to get per-invocation token counts logged at INFO level.
"""

import logging
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

log = logging.getLogger(__name__)


class UsageTracker(BaseCallbackHandler):
    """Logs input/output token counts after each LLM call."""

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        usage = getattr(response, "llm_output", {}) or {}
        token_usage = usage.get("usage") or usage.get("token_usage") or {}
        if not token_usage and response.generations:
            # Some providers put usage in generation info
            gen = response.generations[0]
            if gen and hasattr(gen[0], "generation_info"):
                token_usage = (gen[0].generation_info or {}).get("usage", {})

        if token_usage:
            input_tokens = token_usage.get("input_tokens") or token_usage.get("prompt_tokens", 0)
            output_tokens = (
                token_usage.get("output_tokens") or token_usage.get("completion_tokens", 0)
            )
            log.info(
                "Token usage — input: %d, output: %d, total: %d",
                input_tokens,
                output_tokens,
                input_tokens + output_tokens,
            )

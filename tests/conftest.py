"""Pytest fixtures for competitive_intel tests."""

import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def env_config(monkeypatch):
    """Ensure minimal env for tests (avoid loading real .env in CI)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", "test-key"))
    monkeypatch.setenv("COMPETITORS", "TestCo,OtherCo")


@pytest.fixture
def mock_llm_response():
    """Return a mock AIMessage with .content and no .tool_calls."""
    msg = MagicMock()
    msg.content = "# Mock Brief\n\n## Executive Summary\nTest content."
    msg.tool_calls = []
    return msg


@pytest.fixture
def mock_chat_anthropic(mock_llm_response):
    """
    Patch module-level LLM singletons and the retry invokers in each node.

    Nodes now use module-level singleton instances (_LLM, _LLM_BASE) constructed
    at import time, and wrap calls in tenacity retry helpers. We patch:
      - The singleton instances directly (so .invoke / .bind_tools etc. are mocked)
      - The _invoke_llm / _invoke_structured retry wrappers (bypass tenacity in tests)
    """
    instance = MagicMock()
    instance.invoke.return_value = mock_llm_response
    instance.bind_tools.return_value = instance
    structured = MagicMock()
    instance.with_structured_output.return_value = structured
    structured.invoke.return_value = mock_llm_response  # default; tests override as needed

    def make_invoke_llm_with_llm_arg(inst):
        """For research node: _invoke_llm(llm, messages)"""
        def _invoke_llm(llm, messages):
            return inst.invoke(messages)
        return _invoke_llm

    def make_invoke_llm_no_llm_arg(inst):
        """For writer node: _invoke_llm(messages)"""
        def _invoke_llm(messages):
            return inst.invoke(messages)
        return _invoke_llm

    def make_invoke_structured(inst):
        def _invoke_structured(llm, messages):
            return structured.invoke(messages)
        return _invoke_structured

    with (
        # Patch singleton LLM objects in each node module
        patch("competitive_intel.nodes.critic._LLM", instance),
        patch("competitive_intel.nodes.writer._LLM", instance),
        patch("competitive_intel.nodes.research._LLM_BASE", instance),
        # Bypass tenacity retry wrappers — tests should not sleep or retry
        patch(
            "competitive_intel.nodes.critic._invoke_structured",
            make_invoke_structured(instance),
        ),
        patch(
            "competitive_intel.nodes.writer._invoke_llm",
            make_invoke_llm_no_llm_arg(instance),
        ),
        patch(
            "competitive_intel.nodes.research._invoke_llm",
            make_invoke_llm_with_llm_arg(instance),
        ),
        patch(
            "competitive_intel.nodes.research._invoke_structured",
            make_invoke_structured(instance),
        ),
    ):
        yield MagicMock(), instance, structured

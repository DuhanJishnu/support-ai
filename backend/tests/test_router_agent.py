"""Tests for Day 8: Triage & Router Agent.

These tests use mocking so they do NOT require a real GOOGLE_API_KEY.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import ValidationError

from app.agents.nodes.router import route_after_router, router_node
from app.agents.nodes.stubs import (
    billing_agent_node,
    general_agent_node,
    telemetry_agent_node,
)
from app.agents.schemas import IntentClassification
from app.agents.state import AgentState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_state(
    message: str = "help me", extra_context: dict[str, Any] | None = None
) -> AgentState:
    """Return a minimal AgentState with one HumanMessage."""
    return AgentState(
        messages=[HumanMessage(content=message)],
        gathered_context=extra_context or {},
    )


# ---------------------------------------------------------------------------
# Schema Tests
# ---------------------------------------------------------------------------


class TestIntentClassification:
    def test_valid_billing_intent(self):
        result = IntentClassification(
            intent="BILLING", urgency=3, reasoning="double charge"
        )
        assert result.intent == "BILLING"
        assert result.urgency == 3

    def test_valid_safety_intent(self):
        result = IntentClassification(
            intent="SAFETY", urgency=5, reasoning="driver went off route"
        )
        assert result.intent == "SAFETY"
        assert result.urgency == 5

    def test_valid_general_intent(self):
        result = IntentClassification(
            intent="GENERAL", urgency=1, reasoning="asking about promo"
        )
        assert result.intent == "GENERAL"

    def test_urgency_below_range_fails(self):
        with pytest.raises(ValidationError):
            IntentClassification(intent="GENERAL", urgency=0, reasoning="test")

    def test_urgency_above_range_fails(self):
        with pytest.raises(ValidationError):
            IntentClassification(intent="GENERAL", urgency=6, reasoning="test")

    def test_invalid_intent_fails(self):
        with pytest.raises(ValidationError):
            IntentClassification(intent="UNKNOWN", urgency=2, reasoning="test")  # type: ignore


# ---------------------------------------------------------------------------
# Router Node Tests (with mocked LLM)
# ---------------------------------------------------------------------------

MOCK_BILLING = IntentClassification(
    intent="BILLING", urgency=3, reasoning="User reports double charge."
)
MOCK_SAFETY = IntentClassification(
    intent="SAFETY", urgency=4, reasoning="Driver deviated from route."
)
MOCK_GENERAL = IntentClassification(
    intent="GENERAL", urgency=1, reasoning="User asks for promo code info."
)


class TestRouterNode:
    @patch("app.agents.nodes.router.get_router_llm")
    def test_router_classifies_billing(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MOCK_BILLING
        mock_get_llm.return_value = mock_llm

        state = make_state("You charged me twice for the same ride!")
        result = router_node(state)

        assert result.gathered_context["intent"] == "BILLING"
        assert result.gathered_context["urgency"] == 3
        assert result.current_node == "router"
        assert result.resolution_status == "in_progress"

    @patch("app.agents.nodes.router.get_router_llm")
    def test_router_classifies_safety(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MOCK_SAFETY
        mock_get_llm.return_value = mock_llm

        state = make_state("My driver went off the normal route and I feel unsafe!")
        result = router_node(state)

        assert result.gathered_context["intent"] == "SAFETY"
        assert result.gathered_context["urgency"] == 4

    @patch("app.agents.nodes.router.get_router_llm")
    def test_router_classifies_general(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MOCK_GENERAL
        mock_get_llm.return_value = mock_llm

        state = make_state("How do I apply a promo code?")
        result = router_node(state)

        assert result.gathered_context["intent"] == "GENERAL"
        assert result.gathered_context["urgency"] == 1

    @patch("app.agents.nodes.router.get_router_llm")
    def test_router_fallback_on_llm_error(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("LLM unavailable")
        mock_get_llm.return_value = mock_llm

        state = make_state("I have a problem")
        result = router_node(state)

        # Should fall back to GENERAL with urgency 1
        assert result.gathered_context["intent"] == "GENERAL"
        assert result.gathered_context["urgency"] == 1

    def test_router_no_human_message_fallback(self):
        """If no HumanMessage is present, router should not crash."""
        state = AgentState(messages=[AIMessage(content="hello")], gathered_context={})
        result = router_node(state)
        assert result.gathered_context["intent"] == "GENERAL"


# ---------------------------------------------------------------------------
# Conditional Edge Tests
# ---------------------------------------------------------------------------


class TestRouteAfterRouter:
    def test_routes_billing_intent(self):
        state = make_state(extra_context={"intent": "BILLING"})
        assert route_after_router(state) == "billing_agent"

    def test_routes_safety_intent(self):
        state = make_state(extra_context={"intent": "SAFETY"})
        assert route_after_router(state) == "telemetry_agent"

    def test_routes_general_intent(self):
        state = make_state(extra_context={"intent": "GENERAL"})
        assert route_after_router(state) == "general_agent"

    def test_routes_unknown_intent_to_general(self):
        state = make_state(extra_context={"intent": "UNKNOWN"})
        assert route_after_router(state) == "general_agent"

    def test_routes_missing_intent_to_general(self):
        state = make_state()
        assert route_after_router(state) == "general_agent"


# ---------------------------------------------------------------------------
# Stub Agent Node Tests
# ---------------------------------------------------------------------------


class TestStubNodes:
    def _state_with_intent(self, intent: str, urgency: int = 2) -> AgentState:
        return make_state(
            extra_context={"intent": intent, "urgency": urgency},
        )

    def test_billing_stub_appends_message(self):
        state = self._state_with_intent("BILLING", urgency=3)
        result = billing_agent_node(state)
        assert len(result.messages) == 2  # HumanMessage + AIMessage stub
        assert isinstance(result.messages[-1], AIMessage)
        assert "BillingAgent" in result.messages[-1].content
        assert result.current_node == "billingagent"

    def test_telemetry_stub_appends_message(self):
        state = self._state_with_intent("SAFETY", urgency=4)
        result = telemetry_agent_node(state)
        assert "TelemetryAgent" in result.messages[-1].content
        assert result.current_node == "telemetryagent"

    def test_general_stub_appends_message(self):
        state = self._state_with_intent("GENERAL", urgency=1)
        result = general_agent_node(state)
        assert "GeneralAgent" in result.messages[-1].content
        assert result.current_node == "generalagent"


# ---------------------------------------------------------------------------
# Full Graph Integration Test (mocked LLM)
# ---------------------------------------------------------------------------


class TestFullGraph:
    @patch("app.agents.nodes.router.get_router_llm")
    def test_billing_flow_end_to_end(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MOCK_BILLING
        mock_get_llm.return_value = mock_llm

        from app.agents.graph import run_support_graph

        result = run_support_graph("I was charged twice for my last ride.")

        assert result.gathered_context["intent"] == "BILLING"
        assert result.current_node == "billingagent"
        assert result.resolution_status == "in_progress"
        assert len(result.messages) == 2

    @patch("app.agents.nodes.router.get_router_llm")
    def test_safety_flow_end_to_end(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MOCK_SAFETY
        mock_get_llm.return_value = mock_llm

        from app.agents.graph import run_support_graph

        result = run_support_graph("My driver is taking a very strange route!")

        assert result.gathered_context["intent"] == "SAFETY"
        assert result.current_node == "telemetryagent"

    @patch("app.agents.nodes.router.get_router_llm")
    def test_general_flow_end_to_end(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MOCK_GENERAL
        mock_get_llm.return_value = mock_llm

        from app.agents.graph import run_support_graph

        result = run_support_graph("How do I update my payment method?")

        assert result.gathered_context["intent"] == "GENERAL"
        assert result.current_node == "generalagent"

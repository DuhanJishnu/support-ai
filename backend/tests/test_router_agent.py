"""Tests for Day 8: Triage & Router Agent.

These tests use mocking so they do NOT require a real GOOGLE_API_KEY.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import ValidationError

from app.agents.nodes.guardrails import guardrail_node
from app.agents.nodes.router import route_after_router, router_node
from app.agents.nodes.stubs import (
    billing_agent_node,
    generic_llm_node,
    telemetry_agent_node,
)
from app.agents.schemas import IntentClassification, ResolutionDecision
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
            IntentClassification(
                intent="UNKNOWN",
                urgency=2,
                reasoning="test",
            )  # type: ignore


class TestResolutionDecision:
    def test_valid_refund_resolution(self):
        result = ResolutionDecision(
            action="ISSUE_REFUND",
            amount=12.5,
            reason="Duplicate charge detected.",
        )
        assert result.action == "ISSUE_REFUND"
        assert result.amount == 12.5

    def test_invalid_negative_amount_fails(self):
        with pytest.raises(ValidationError):
            ResolutionDecision(
                action="ISSUE_REFUND",
                amount=-1,
                reason="Invalid refund.",
            )


class TestGuardrailNode:
    def test_guardrail_allows_small_refund(self):
        state = make_state(
            extra_context={
                "intent": "BILLING",
                "urgency": 3,
                "proposed_resolution": {
                    "action": "ISSUE_REFUND",
                    "amount": 12.5,
                    "reason": "Duplicate charge detected.",
                },
            }
        )

        result = guardrail_node(state)

        assert result.current_node == "guardrail"
        assert result.resolution_status == "resolved"
        assert result.gathered_context["resolution"]["action"] == "ISSUE_REFUND"

    def test_guardrail_escalates_large_refund(self):
        state = make_state(
            extra_context={
                "intent": "BILLING",
                "urgency": 3,
                "proposed_resolution": {
                    "action": "ISSUE_REFUND",
                    "amount": 75.0,
                    "reason": "Large refund request.",
                },
            }
        )

        result = guardrail_node(state)

        assert result.current_node == "guardrail"
        assert result.resolution_status == "needs_human"
        assert result.gathered_context["resolution"]["action"] == "ESCALATE"


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
        assert route_after_router(state) == "generic_llm"

    def test_routes_unknown_intent_to_general(self):
        state = make_state(extra_context={"intent": "UNKNOWN"})
        assert route_after_router(state) == "generic_llm"

    def test_routes_missing_intent_to_general(self):
        state = make_state()
        assert route_after_router(state) == "generic_llm"


# ---------------------------------------------------------------------------
# Tool Agent Node Tests
# ---------------------------------------------------------------------------


class TestToolAgentNodes:
    def _state_with_intent(self, intent: str, urgency: int = 2) -> AgentState:
        return make_state(
            extra_context={"intent": intent, "urgency": urgency},
        )

    @patch("app.agents.nodes.stubs._invoke_mcp_tool")
    def test_billing_agent_invokes_transaction_tool(self, mock_invoke_tool):
        mock_invoke_tool.return_value = {
            "data": {"transaction_id": "txn_123", "status": "SUCCESS"}
        }
        state = make_state(
            "Please check transaction_id txn_123",
            {"intent": "BILLING", "urgency": 3},
        )

        result = billing_agent_node(state)

        mock_invoke_tool.assert_called_once_with(
            "verify_transaction_status",
            {"transaction_id": "txn_123"},
        )
        assert len(result.messages) == 2
        assert isinstance(result.messages[-1], AIMessage)
        assert "BillingAgent" in result.messages[-1].content
        assert result.current_node == "billing_agent"
        assert result.gathered_context["last_tool_call"]["status"] == "succeeded"
        assert (
            result.gathered_context["billing"]["result"]["data"]["status"] == "SUCCESS"
        )

    @patch("app.agents.nodes.stubs._invoke_mcp_tool")
    def test_telemetry_agent_invokes_route_tool(self, mock_invoke_tool):
        mock_invoke_tool.return_value = {
            "data": {"ride_id": "ride_456", "deviation_score": 0.85}
        }
        state = make_state(
            "Driver went off route on ride_id ride_456",
            {"intent": "SAFETY", "urgency": 4},
        )

        result = telemetry_agent_node(state)

        mock_invoke_tool.assert_called_once_with(
            "get_ride_route_deviation",
            {"ride_id": "ride_456"},
        )
        assert "TelemetryAgent" in result.messages[-1].content
        assert result.current_node == "telemetry_agent"
        assert result.gathered_context["last_tool_call"]["status"] == "succeeded"
        assert (
            result.gathered_context["telemetry"]["result"]["data"]["deviation_score"]
            == 0.85
        )

    @patch("app.agents.nodes.stubs._invoke_mcp_tool")
    def test_tool_agent_records_failed_tool_call(self, mock_invoke_tool):
        mock_invoke_tool.side_effect = RuntimeError("MCP client is not initialized")
        state = self._state_with_intent("BILLING", urgency=3)

        result = billing_agent_node(state)

        assert result.current_node == "billing_agent"
        assert result.gathered_context["last_tool_call"]["status"] == "failed"
        assert (
            "MCP client is not initialized"
            in result.gathered_context["billing"]["result"]["error"]
        )

    def test_general_stub_appends_message(self):
        state = self._state_with_intent("GENERAL", urgency=1)
        result = generic_llm_node(state)
        assert "GenericLLM" in result.messages[-1].content
        assert result.current_node == "generic_llm"


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
        assert result.current_node == "guardrail"
        assert result.resolution_status == "resolved"
        assert result.gathered_context["last_node"] == "billing_agent"
        assert result.gathered_context["resolution"]["action"] == "NO_ACTION"
        assert len(result.messages) == 2
        assert result.gathered_context["last_tool_call"]["tool_name"] == (
            "verify_transaction_status"
        )

    @patch("app.agents.nodes.router.get_router_llm")
    def test_safety_flow_end_to_end(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MOCK_SAFETY
        mock_get_llm.return_value = mock_llm

        from app.agents.graph import run_support_graph

        result = run_support_graph("My driver is taking a very strange route!")

        assert result.gathered_context["intent"] == "SAFETY"
        assert result.current_node == "guardrail"
        assert result.resolution_status == "resolved"
        assert result.gathered_context["last_node"] == "telemetry_agent"
        assert result.gathered_context["resolution"]["action"] == "NO_ACTION"
        assert result.gathered_context["last_tool_call"]["tool_name"] == (
            "get_ride_route_deviation"
        )

    @patch("app.agents.nodes.router.get_router_llm")
    def test_general_flow_end_to_end(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MOCK_GENERAL
        mock_get_llm.return_value = mock_llm

        from app.agents.graph import run_support_graph

        result = run_support_graph("How do I update my payment method?")

        assert result.gathered_context["intent"] == "GENERAL"
        assert result.current_node == "guardrail"
        assert result.resolution_status == "resolved"
        assert result.gathered_context["last_node"] == "generic_llm"
        assert result.gathered_context["resolution"]["action"] == "NO_ACTION"

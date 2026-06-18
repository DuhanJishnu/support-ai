"""End-to-end workflow tests for the support agent graph.

Covers multi-turn conversation memory, refund request flows,
duplicate-charge detection, guardrail policy decisions, and
full graph state transition verification.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.graph import run_support_graph
from app.agents.nodes.billing_decision import billing_decision_node
from app.agents.nodes.guardrails import guardrail_node
from app.agents.schemas import IntentClassification
from app.agents.state import AgentState

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

MOCK_BILLING = IntentClassification(
    intent="BILLING", urgency=3, reasoning="Billing dispute detected."
)
MOCK_GENERAL = IntentClassification(
    intent="GENERAL", urgency=1, reasoning="General inquiry."
)

MCP_TXN_SUCCESS = {
    "data": {
        "transaction_id": "txn_xyz",
        "status": "SUCCESS",
        "amount": 25.50,
        "currency": "USD",
        "payment_method": "Credit Card",
    }
}


def _mock_router(mock_get_llm: MagicMock, classification: IntentClassification):
    """Wire up the router LLM mock to return a fixed classification."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = classification
    mock_get_llm.return_value = mock_llm


def _make_state(
    message: str = "help me",
    extra_context: dict[str, Any] | None = None,
    entities: dict[str, Any] | None = None,
) -> AgentState:
    """Return a minimal AgentState with one HumanMessage."""
    return AgentState(
        messages=[HumanMessage(content=message)],
        gathered_context=extra_context or {},
        extracted_entities=entities or {},
    )


# ===================================================================
# 1. Multi-turn transaction memory
# ===================================================================


class TestMultiTurnTransactionMemory:
    """Verify that a transaction ID mentioned in turn 1 is carried into turn 2
    when the user references 'that transaction' without repeating the ID."""

    @patch("app.agents.nodes.stubs._invoke_mcp_tool")
    @patch("app.agents.nodes.router.get_router_llm")
    def test_entity_persists_across_turns(self, mock_get_llm, mock_mcp):
        """Turn 1 mentions txn_abc123 → Turn 2 says 'that transaction'
        → billing_agent should still use txn_abc123."""
        _mock_router(mock_get_llm, MOCK_BILLING)
        mock_mcp.return_value = MCP_TXN_SUCCESS

        # ---- Turn 1: user explicitly mentions the transaction ----
        turn1 = run_support_graph(
            message="I have a problem with txn_abc123",
            conversation_id="conv_multi_01",
        )

        # The billing_agent should have extracted the ID
        assert turn1.extracted_entities.get("transaction_id") == "txn_abc123"

        # ---- Turn 2: user says 'that transaction' (no explicit ID) ----
        previous_msgs = [
            {"type": "human", "content": "I have a problem with txn_abc123"},
            {"type": "ai", "content": turn1.messages[-1].content},
        ]
        turn2 = run_support_graph(
            message="Can you check that transaction again?",
            previous_messages=previous_msgs,
            extracted_entities=turn1.extracted_entities,
            conversation_id="conv_multi_01",
        )

        # The same txn_abc123 should be used thanks to extracted_entities
        assert turn2.extracted_entities.get("transaction_id") == "txn_abc123"
        assert turn2.gathered_context["billing"]["input"]["transaction_id"] == "txn_abc123"

    @patch("app.agents.nodes.stubs._invoke_mcp_tool")
    @patch("app.agents.nodes.router.get_router_llm")
    def test_explicit_id_overrides_entity_memory(self, mock_get_llm, mock_mcp):
        """If turn 2 mentions a *new* transaction ID, it should override memory."""
        _mock_router(mock_get_llm, MOCK_BILLING)
        mock_mcp.return_value = MCP_TXN_SUCCESS

        # Turn 1 with txn_abc123
        turn1 = run_support_graph(
            message="Check txn_abc123 please",
            conversation_id="conv_multi_02",
        )
        assert turn1.extracted_entities["transaction_id"] == "txn_abc123"

        # Turn 2 with a new explicit ID txn_new_999
        turn2 = run_support_graph(
            message="Actually, check txn_new_999 instead",
            extracted_entities=turn1.extracted_entities,
            conversation_id="conv_multi_02",
        )
        assert turn2.extracted_entities["transaction_id"] == "txn_new_999"


# ===================================================================
# 2. Refund request referencing previous messages
# ===================================================================


class TestRefundWithPriorContext:
    """User asks about a transaction in turn 1, then requests a refund in turn 2."""

    @patch("app.agents.nodes.stubs._invoke_mcp_tool")
    @patch("app.agents.nodes.router.get_router_llm")
    def test_refund_uses_transaction_from_prior_turn(self, mock_get_llm, mock_mcp):
        _mock_router(mock_get_llm, MOCK_BILLING)
        mock_mcp.return_value = MCP_TXN_SUCCESS

        # Turn 1: inquiry
        turn1 = run_support_graph(
            message="What happened with txn_refund_42?",
            conversation_id="conv_refund_01",
        )
        assert turn1.extracted_entities.get("transaction_id") == "txn_refund_42"

        # Turn 2: request refund (no explicit txn ID)
        previous_msgs = [
            {"type": "human", "content": "What happened with txn_refund_42?"},
            {"type": "ai", "content": turn1.messages[-1].content},
        ]
        turn2 = run_support_graph(
            message="I'd like a refund for that charge",
            previous_messages=previous_msgs,
            extracted_entities=turn1.extracted_entities,
            conversation_id="conv_refund_01",
        )

        # billing_decision should propose ISSUE_REFUND because 'refund' keyword
        assert turn2.gathered_context["resolution"]["action"] == "ISSUE_REFUND"
        assert turn2.gathered_context["resolution"]["amount"] == 25.50
        # Should resolve because $25.50 ≤ $50 limit
        assert turn2.resolution_status == "resolved"
        # Still using the correct transaction
        assert turn2.extracted_entities["transaction_id"] == "txn_refund_42"


# ===================================================================
# 3. Duplicate charge scenario
# ===================================================================


class TestDuplicateCharge:
    """User says 'I was charged twice for txn_dup_001' → ISSUE_REFUND."""

    @patch("app.agents.nodes.stubs._invoke_mcp_tool")
    @patch("app.agents.nodes.router.get_router_llm")
    def test_duplicate_charge_triggers_refund(self, mock_get_llm, mock_mcp):
        _mock_router(mock_get_llm, MOCK_BILLING)
        mock_mcp.return_value = {
            "data": {
                "transaction_id": "txn_dup_001",
                "status": "SUCCESS",
                "amount": 25.50,
                "currency": "USD",
                "payment_method": "Credit Card",
            }
        }

        result = run_support_graph("I was charged twice for txn_dup_001")

        assert result.gathered_context["intent"] == "BILLING"
        assert result.gathered_context["resolution"]["action"] == "ISSUE_REFUND"
        assert result.gathered_context["resolution"]["amount"] == 25.50
        assert result.resolution_status == "resolved"
        assert result.extracted_entities["transaction_id"] == "txn_dup_001"

    @patch("app.agents.nodes.stubs._invoke_mcp_tool")
    @patch("app.agents.nodes.router.get_router_llm")
    def test_duplicate_charge_large_amount_escalates(self, mock_get_llm, mock_mcp):
        """Duplicate charge > $50 → guardrail escalates to needs_human."""
        _mock_router(mock_get_llm, MOCK_BILLING)
        mock_mcp.return_value = {
            "data": {
                "transaction_id": "txn_dup_big",
                "status": "SUCCESS",
                "amount": 120.00,
                "currency": "USD",
                "payment_method": "Credit Card",
            }
        }

        result = run_support_graph("I was charged twice for txn_dup_big")

        # billing_decision proposes ISSUE_REFUND but amount > $50
        assert result.gathered_context["resolution"]["action"] == "ESCALATE"
        assert result.resolution_status == "needs_human"


# ===================================================================
# 4. Guardrail decision matrix (unit-level)
# ===================================================================


class TestGuardrailDecisions:
    """Verify every guardrail outcome from the decision table."""

    def test_issue_refund_within_limit_resolves(self):
        """ISSUE_REFUND ≤ $50 → resolved."""
        state = _make_state(extra_context={
            "intent": "BILLING",
            "proposed_resolution": {
                "action": "ISSUE_REFUND",
                "amount": 50.00,
                "reason": "Approved refund.",
            },
        })
        result = guardrail_node(state)
        assert result.resolution_status == "resolved"
        assert result.gathered_context["resolution"]["action"] == "ISSUE_REFUND"

    def test_issue_refund_over_limit_needs_human(self):
        """ISSUE_REFUND > $50 → needs_human (ESCALATE)."""
        state = _make_state(extra_context={
            "intent": "BILLING",
            "proposed_resolution": {
                "action": "ISSUE_REFUND",
                "amount": 50.01,
                "reason": "Large refund.",
            },
        })
        result = guardrail_node(state)
        assert result.resolution_status == "needs_human"
        assert result.gathered_context["resolution"]["action"] == "ESCALATE"

    def test_review_case_in_progress(self):
        """REVIEW_CASE → in_progress."""
        state = _make_state(extra_context={
            "intent": "BILLING",
            "proposed_resolution": {
                "action": "REVIEW_CASE",
                "amount": 0.0,
                "reason": "Needs review.",
            },
        })
        result = guardrail_node(state)
        assert result.resolution_status == "in_progress"
        assert result.gathered_context["resolution"]["action"] == "REVIEW_CASE"

    def test_escalate_needs_human(self):
        """ESCALATE → needs_human."""
        state = _make_state(extra_context={
            "intent": "BILLING",
            "proposed_resolution": {
                "action": "ESCALATE",
                "amount": 0.0,
                "reason": "Tool error.",
            },
        })
        result = guardrail_node(state)
        assert result.resolution_status == "needs_human"
        assert result.gathered_context["resolution"]["action"] == "ESCALATE"

    def test_no_action_billing_in_progress(self):
        """NO_ACTION on BILLING intent → in_progress."""
        state = _make_state(extra_context={
            "intent": "BILLING",
            "proposed_resolution": {
                "action": "NO_ACTION",
                "amount": 0.0,
                "reason": "No action needed.",
            },
        })
        result = guardrail_node(state)
        assert result.resolution_status == "in_progress"
        assert result.gathered_context["resolution"]["action"] == "NO_ACTION"

    def test_no_action_general_resolved(self):
        """NO_ACTION on GENERAL intent → resolved."""
        state = _make_state(extra_context={
            "intent": "GENERAL",
            "proposed_resolution": {
                "action": "NO_ACTION",
                "amount": 0.0,
                "reason": "No action needed.",
            },
        })
        result = guardrail_node(state)
        assert result.resolution_status == "resolved"
        assert result.gathered_context["resolution"]["action"] == "NO_ACTION"


# ===================================================================
# 5. Full graph state transitions (billing flow)
# ===================================================================


class TestBillingFlowStateTransitions:
    """Trace state through router → billing_agent → billing_decision → guardrail."""

    @patch("app.agents.nodes.stubs._invoke_mcp_tool")
    @patch("app.agents.nodes.router.get_router_llm")
    def test_full_billing_path_states(self, mock_get_llm, mock_mcp):
        """End-to-end billing flow verifies gathered_context at each stage."""
        _mock_router(mock_get_llm, MOCK_BILLING)
        mock_mcp.return_value = MCP_TXN_SUCCESS

        result = run_support_graph("I was charged twice for txn_flow_001")

        # --- Router set intent & urgency ---
        assert result.gathered_context["intent"] == "BILLING"
        assert result.gathered_context["urgency"] == 3

        # --- billing_agent called MCP tool ---
        assert result.gathered_context["last_node"] == "billing_agent"
        assert result.gathered_context["last_tool_call"]["tool_name"] == "verify_transaction_status"
        assert result.gathered_context["last_tool_call"]["status"] == "succeeded"
        assert result.gathered_context["billing"]["result"]["data"]["status"] == "SUCCESS"

        # --- billing_decision proposed ISSUE_REFUND ---
        assert result.gathered_context["billing_decision"]["is_duplicate_claim"] is True
        assert result.gathered_context["billing_decision"]["txn_status"] == "SUCCESS"
        assert result.gathered_context["billing_decision"]["txn_amount"] == 25.50

        # --- guardrail finalized (amount ≤ $50) ---
        assert result.current_node == "guardrail"
        assert result.gathered_context["resolution"]["action"] == "ISSUE_REFUND"
        assert result.gathered_context["resolution"]["amount"] == 25.50
        assert result.resolution_status == "resolved"

    @patch("app.agents.nodes.stubs._invoke_mcp_tool")
    @patch("app.agents.nodes.router.get_router_llm")
    def test_billing_with_pending_transaction(self, mock_get_llm, mock_mcp):
        """PENDING transaction → billing_decision proposes REVIEW_CASE → in_progress."""
        _mock_router(mock_get_llm, MOCK_BILLING)
        mock_mcp.return_value = {
            "data": {
                "transaction_id": "txn_pending",
                "status": "PENDING",
                "amount": 15.00,
                "currency": "USD",
                "payment_method": "Debit Card",
            }
        }

        result = run_support_graph("I was charged twice for txn_pending")

        assert result.gathered_context["billing_decision"]["txn_status"] == "PENDING"
        assert result.gathered_context["resolution"]["action"] == "REVIEW_CASE"
        assert result.resolution_status == "in_progress"

    @patch("app.agents.nodes.stubs._invoke_mcp_tool")
    @patch("app.agents.nodes.router.get_router_llm")
    def test_billing_with_failed_transaction(self, mock_get_llm, mock_mcp):
        """FAILED transaction → NO_ACTION, but BILLING intent → in_progress."""
        _mock_router(mock_get_llm, MOCK_BILLING)
        mock_mcp.return_value = {
            "data": {
                "transaction_id": "txn_failed",
                "status": "FAILED",
                "amount": 30.00,
                "currency": "USD",
                "payment_method": "Credit Card",
            }
        }

        result = run_support_graph("I was charged for txn_failed")

        assert result.gathered_context["billing_decision"]["txn_status"] == "FAILED"
        assert result.gathered_context["resolution"]["action"] == "NO_ACTION"
        # NO_ACTION + BILLING → in_progress
        assert result.resolution_status == "in_progress"

    @patch("app.agents.nodes.stubs._invoke_mcp_tool")
    @patch("app.agents.nodes.router.get_router_llm")
    def test_billing_with_tool_error_escalates(self, mock_get_llm, mock_mcp):
        """MCP tool error → billing_decision proposes ESCALATE → needs_human."""
        _mock_router(mock_get_llm, MOCK_BILLING)
        mock_mcp.side_effect = RuntimeError("MCP client is not initialized")

        result = run_support_graph("I was charged twice for txn_error_01")

        assert result.gathered_context["last_tool_call"]["status"] == "failed"
        assert result.gathered_context["resolution"]["action"] == "ESCALATE"
        assert result.resolution_status == "needs_human"

    @patch("app.agents.nodes.stubs._invoke_mcp_tool")
    @patch("app.agents.nodes.router.get_router_llm")
    def test_billing_message_count(self, mock_get_llm, mock_mcp):
        """Billing flow produces 2 messages: human + billing_agent AI response."""
        _mock_router(mock_get_llm, MOCK_BILLING)
        mock_mcp.return_value = MCP_TXN_SUCCESS

        result = run_support_graph("I was charged twice for txn_count_01")

        # 1 HumanMessage + 1 AIMessage from billing_agent
        assert len(result.messages) == 2
        assert result.messages[0].type == "human"
        assert result.messages[1].type == "ai"
        assert "BillingAgent" in result.messages[1].content


# ===================================================================
# Billing decision node (unit-level)
# ===================================================================


class TestBillingDecisionNode:
    """Direct tests for billing_decision_node logic."""

    def _state_with_billing_result(
        self,
        message: str,
        txn_data: dict[str, Any],
    ) -> AgentState:
        return AgentState(
            messages=[HumanMessage(content=message)],
            gathered_context={
                "intent": "BILLING",
                "urgency": 3,
                "billing": {
                    "tool": "verify_transaction_status",
                    "input": {"transaction_id": txn_data.get("transaction_id", "txn_x")},
                    "result": {"data": txn_data},
                },
            },
        )

    def test_duplicate_claim_success_issues_refund(self):
        state = self._state_with_billing_result(
            "I was charged twice for this ride",
            {"transaction_id": "txn_d1", "status": "SUCCESS", "amount": 20.0},
        )
        result = billing_decision_node(state)
        assert result.gathered_context["proposed_resolution"]["action"] == "ISSUE_REFUND"
        assert result.gathered_context["proposed_resolution"]["amount"] == 20.0

    def test_refund_keyword_success_issues_refund(self):
        state = self._state_with_billing_result(
            "I want a refund please",
            {"transaction_id": "txn_r1", "status": "SUCCESS", "amount": 10.0},
        )
        result = billing_decision_node(state)
        assert result.gathered_context["proposed_resolution"]["action"] == "ISSUE_REFUND"

    def test_pending_transaction_reviews_case(self):
        state = self._state_with_billing_result(
            "I was charged twice",
            {"transaction_id": "txn_p1", "status": "PENDING", "amount": 10.0},
        )
        result = billing_decision_node(state)
        assert result.gathered_context["proposed_resolution"]["action"] == "REVIEW_CASE"

    def test_failed_transaction_no_action(self):
        state = self._state_with_billing_result(
            "I want a refund",
            {"transaction_id": "txn_f1", "status": "FAILED", "amount": 5.0},
        )
        result = billing_decision_node(state)
        assert result.gathered_context["proposed_resolution"]["action"] == "NO_ACTION"

    def test_tool_error_escalates(self):
        state = AgentState(
            messages=[HumanMessage(content="check my billing")],
            gathered_context={
                "intent": "BILLING",
                "billing": {
                    "tool": "verify_transaction_status",
                    "input": {"transaction_id": "txn_e1"},
                    "result": {"error": "MCP client is not initialized"},
                },
            },
        )
        result = billing_decision_node(state)
        assert result.gathered_context["proposed_resolution"]["action"] == "ESCALATE"

    def test_no_clear_signal_reviews_case(self):
        """Billing intent but message has no refund/duplicate keywords → REVIEW_CASE."""
        state = self._state_with_billing_result(
            "I have a question about my payment",
            {"transaction_id": "txn_q1", "status": "SUCCESS", "amount": 15.0},
        )
        result = billing_decision_node(state)
        assert result.gathered_context["proposed_resolution"]["action"] == "REVIEW_CASE"

    def test_billing_decision_sets_current_node(self):
        state = self._state_with_billing_result(
            "I was charged twice",
            {"transaction_id": "txn_n1", "status": "SUCCESS", "amount": 10.0},
        )
        result = billing_decision_node(state)
        assert result.current_node == "billing_decision"

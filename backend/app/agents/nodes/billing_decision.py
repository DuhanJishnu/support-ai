"""Billing decision engine — evaluates tool results to produce a proposed_resolution."""

import re
from typing import Any

import structlog

from app.agents.state import AgentState, coerce_agent_state

logger = structlog.get_logger()

# Keywords that indicate the user is requesting a refund
_REFUND_KEYWORDS = re.compile(
    r"refund|overcharge|wrong\s*amount|too\s*much|incorrect\s*charge|money\s*back",
    re.IGNORECASE,
)

# Keywords that indicate a duplicate / double charge
_DUPLICATE_KEYWORDS = re.compile(
    r"charged?\s*twice|double\s*charge|duplicate|two\s*charges?|billed?\s*twice|2x|two\s*times",
    re.IGNORECASE,
)


def _all_human_text(agent_state: AgentState) -> str:
    """Concatenate all human messages into a single search string."""
    from langchain_core.messages import HumanMessage

    return " ".join(
        str(m.content) for m in agent_state.messages if isinstance(m, HumanMessage)
    )


def _extract_billing_data(agent_state: AgentState) -> dict[str, Any]:
    """Pull the billing tool result out of gathered_context."""
    billing = agent_state.gathered_context.get("billing", {})
    result = billing.get("result", {})
    # MCP returns { "data": { ... } } or flat dict
    if isinstance(result, dict) and "data" in result:
        return result["data"]
    return result


def billing_decision_node(state: AgentState | dict[str, Any]) -> AgentState:
    """Evaluate billing data + user intent and produce a proposed_resolution.

    Decision matrix:
    ┌──────────────────────┬────────────────────┬───────────────────────────────┐
    │ User Signal          │ Txn Status         │ Proposed Action               │
    ├──────────────────────┼────────────────────┼───────────────────────────────┤
    │ duplicate / twice    │ SUCCESS            │ ISSUE_REFUND (full amount)    │
    │ refund / overcharge  │ SUCCESS            │ ISSUE_REFUND (full amount)    │
    │ any billing          │ PENDING            │ REVIEW_CASE                   │
    │ any billing          │ FAILED             │ NO_ACTION (already failed)    │
    │ any billing          │ tool error         │ ESCALATE                      │
    │ no clear signal      │ SUCCESS            │ REVIEW_CASE                   │
    └──────────────────────┴────────────────────┴───────────────────────────────┘
    """
    agent_state = coerce_agent_state(state)
    full_text = _all_human_text(agent_state)
    billing_data = _extract_billing_data(agent_state)

    is_refund_request = bool(_REFUND_KEYWORDS.search(full_text))
    is_duplicate_claim = bool(_DUPLICATE_KEYWORDS.search(full_text))

    txn_status = str(billing_data.get("status", "")).upper()
    txn_amount = float(billing_data.get("amount", 0))
    txn_id = str(billing_data.get("transaction_id", "unknown"))

    # If tool returned an error, escalate
    if billing_data.get("error"):
        proposed = {
            "action": "ESCALATE",
            "amount": 0.0,
            "reason": (
                f"Billing tool returned an error for {txn_id}. "
                "Manual investigation required."
            ),
        }
    elif txn_status == "FAILED":
        proposed = {
            "action": "NO_ACTION",
            "amount": 0.0,
            "reason": (
                f"Transaction {txn_id} already has FAILED status. "
                "No charge was applied — no refund needed."
            ),
        }
    elif txn_status == "PENDING":
        proposed = {
            "action": "REVIEW_CASE",
            "amount": 0.0,
            "reason": (
                f"Transaction {txn_id} is still PENDING. "
                "Cannot process refund until payment settles."
            ),
        }
    elif is_duplicate_claim:
        proposed = {
            "action": "ISSUE_REFUND",
            "amount": txn_amount,
            "reason": (
                f"Customer reports duplicate charge for {txn_id}. "
                f"Refund of ${txn_amount:.2f} recommended."
            ),
        }
    elif is_refund_request:
        proposed = {
            "action": "ISSUE_REFUND",
            "amount": txn_amount,
            "reason": (
                f"Customer requests refund for {txn_id} (${txn_amount:.2f}). "
                "Transaction verified as SUCCESS."
            ),
        }
    else:
        # Billing intent but no clear refund/duplicate signal
        proposed = {
            "action": "REVIEW_CASE",
            "amount": 0.0,
            "reason": (
                f"Billing inquiry about {txn_id} requires further review. "
                "No explicit refund or duplicate claim detected."
            ),
        }

    logger.info(
        "BillingDecision: proposed resolution",
        txn_id=txn_id,
        txn_status=txn_status,
        is_refund=is_refund_request,
        is_duplicate=is_duplicate_claim,
        action=proposed["action"],
        amount=proposed["amount"],
    )

    return agent_state.model_copy(
        update={
            "current_node": "billing_decision",
            "gathered_context": {
                **agent_state.gathered_context,
                "proposed_resolution": proposed,
                "billing_decision": {
                    "is_refund_request": is_refund_request,
                    "is_duplicate_claim": is_duplicate_claim,
                    "txn_status": txn_status,
                    "txn_amount": txn_amount,
                },
            },
        }
    )

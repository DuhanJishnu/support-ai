"""Policy guardrails for deterministic support outcomes."""

from typing import Any

import structlog

from app.agents.schemas import ResolutionDecision
from app.agents.state import AgentState, coerce_agent_state

logger = structlog.get_logger()

MAX_REFUND_LIMIT = 50.0


def guardrail_node(state: AgentState | dict[str, Any]) -> AgentState:
    """Validate and finalize a proposed resolution against company policy."""
    agent_state = coerce_agent_state(state)

    proposed = agent_state.gathered_context.get("proposed_resolution")
    if not isinstance(proposed, dict):
        proposed = {
            "action": "NO_ACTION",
            "amount": 0.0,
            "reason": "No proposed resolution supplied.",
        }

    try:
        decision = ResolutionDecision.model_validate(proposed)
    except Exception:
        logger.warning(
            "GuardrailNode: invalid proposed resolution, defaulting to REVIEW_CASE",
            proposed=proposed,
        )
        decision = ResolutionDecision(
            action="REVIEW_CASE",
            amount=0.0,
            reason="Resolution payload was invalid; human review required.",
        )

    if decision.action == "ISSUE_REFUND" and decision.amount > MAX_REFUND_LIMIT:
        final_decision = ResolutionDecision(
            action="ESCALATE",
            amount=decision.amount,
            reason=(
                "Refund exceeds the maximum allowed amount without manager approval."
            ),
        )
        resolution_status = "needs_human"
    else:
        final_decision = decision
        resolution_status = "resolved"

    logger.info(
        "GuardrailNode: final decision selected",
        action=final_decision.action,
        amount=final_decision.amount,
        status=resolution_status,
    )

    return agent_state.model_copy(
        update={
            "current_node": "guardrail",
            "resolution_status": resolution_status,
            "gathered_context": {
                **agent_state.gathered_context,
                "resolution": {
                    "action": final_decision.action,
                    "amount": final_decision.amount,
                    "reason": final_decision.reason,
                },
            },
        }
    )

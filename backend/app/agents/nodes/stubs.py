"""Stub agent nodes for billing, telemetry, and general support queries."""

from typing import Any

import structlog
from langchain_core.messages import AIMessage

from app.agents.state import AgentState, coerce_agent_state

logger = structlog.get_logger()


def _stub_node(label: str, state: AgentState | dict[str, Any]) -> AgentState:
    """Generic stub that acknowledges routing and ends the turn."""
    agent_state = coerce_agent_state(state)
    intent = agent_state.gathered_context.get("intent", "GENERAL")
    urgency = agent_state.gathered_context.get("urgency", 1)

    logger.info(f"{label}: handling request", intent=intent, urgency=urgency)

    response = AIMessage(
        content=(
            f"[{label}] Your request has been received "
            f"(intent={intent}, urgency={urgency}). "
            "A specialized agent will handle this shortly."
        )
    )
    return agent_state.model_copy(
        update={
            "messages": [*agent_state.messages, response],
            "current_node": label.lower().replace(" ", "_"),
            "resolution_status": "in_progress",
        }
    )


def billing_agent_node(state: AgentState | dict[str, Any]) -> AgentState:
    """Stub: Billing sub-agent (to be replaced in Day 9)."""
    return _stub_node("BillingAgent", state)


def telemetry_agent_node(state: AgentState | dict[str, Any]) -> AgentState:
    """Stub: Telemetry/Safety sub-agent (to be replaced in Day 9)."""
    return _stub_node("TelemetryAgent", state)


def generic_llm_node(state: AgentState | dict[str, Any]) -> AgentState:
    """Stub: Generic LLM support sub-agent."""
    agent_state = coerce_agent_state(state)
    intent = agent_state.gathered_context.get("intent", "GENERAL")
    urgency = agent_state.gathered_context.get("urgency", 1)

    logger.info(f"GenericLLM: handling request", intent=intent, urgency=urgency)

    response = AIMessage(
        content=(
            f"[GenericLLM] Your request has been received "
            f"(intent={intent}, urgency={urgency}). "
            "A specialized agent will handle this shortly."
        )
    )
    return agent_state.model_copy(
        update={
            "messages": [*agent_state.messages, response],
            "current_node": "generic_llm",
            "resolution_status": "in_progress",
            "gathered_context": {
                **agent_state.gathered_context,
                "last_node": "generic_llm",
            },
        }
    )

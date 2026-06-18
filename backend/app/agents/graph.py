"""Core LangGraph workflow for the support agent system."""

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, StateGraph

from app.agents.nodes.billing_decision import billing_decision_node
from app.agents.nodes.guardrails import guardrail_node
from app.agents.nodes.router import route_after_router, router_node
from app.agents.nodes.stubs import (
    billing_agent_node,
    generic_llm_node,
    telemetry_agent_node,
)
from app.agents.state import AgentState, coerce_agent_state


def build_support_graph():
    """Build and compile the support-agent LangGraph with router and sub-agent stubs."""
    graph = StateGraph(AgentState)

    # --- Nodes ---
    graph.add_node("router", router_node)
    graph.add_node("billing_agent", billing_agent_node)
    graph.add_node("billing_decision", billing_decision_node)
    graph.add_node("telemetry_agent", telemetry_agent_node)
    graph.add_node("generic_llm", generic_llm_node)
    graph.add_node("guardrail", guardrail_node)

    # --- Entry point ---
    graph.set_entry_point("router")

    # --- Conditional edges from router ---
    graph.add_conditional_edges(
        "router",
        route_after_router,
        {
            "billing_agent": "billing_agent",
            "telemetry_agent": "telemetry_agent",
            "generic_llm": "generic_llm",
        },
    )

    # --- Billing goes through decision engine before guardrail ---
    graph.add_edge("billing_agent", "billing_decision")
    graph.add_edge("billing_decision", "guardrail")

    # --- Other agents go directly to guardrail ---
    graph.add_edge("telemetry_agent", "guardrail")
    graph.add_edge("generic_llm", "guardrail")
    graph.add_edge("guardrail", END)

    return graph.compile()


def _rebuild_messages(
    previous_messages: list[dict[str, Any]] | None,
    current_message: str,
) -> list[HumanMessage | AIMessage]:
    """Reconstruct a LangChain message list from serialized history + new message."""
    messages: list[HumanMessage | AIMessage] = []
    for msg in previous_messages or []:
        msg_type = msg.get("type", "human")
        content = str(msg.get("content", ""))
        if msg_type == "ai":
            messages.append(AIMessage(content=content))
        else:
            messages.append(HumanMessage(content=content))
    messages.append(HumanMessage(content=current_message))
    return messages


def run_support_graph(
    message: str,
    gathered_context: dict[str, Any] | None = None,
    previous_messages: list[dict[str, Any]] | None = None,
    extracted_entities: dict[str, Any] | None = None,
    conversation_id: str = "",
) -> AgentState:
    """Run the support graph with conversation history.

    Args:
        message: The current user message.
        gathered_context: Seed context (e.g. ticket_id, channel).
        previous_messages: Serialized messages from prior turns.
        extracted_entities: Entities (transaction_id, ride_id) from prior turns.
        conversation_id: Session identifier for multi-turn tracking.
    """
    graph = build_support_graph()
    all_messages = _rebuild_messages(previous_messages, message)
    initial_state = AgentState(
        messages=all_messages,
        gathered_context=gathered_context or {},
        extracted_entities=extracted_entities or {},
        conversation_id=conversation_id,
    )
    return coerce_agent_state(graph.invoke(initial_state))

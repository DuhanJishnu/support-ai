"""Core LangGraph workflow for the support agent system."""

from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph

from app.agents.nodes.router import route_after_router, router_node
from app.agents.nodes.stubs import (
    billing_agent_node,
    general_agent_node,
    telemetry_agent_node,
)
from app.agents.state import AgentState, coerce_agent_state


def build_support_graph():
    """Build and compile the support-agent LangGraph with router and sub-agent stubs."""
    graph = StateGraph(AgentState)

    # --- Nodes ---
    graph.add_node("router", router_node)
    graph.add_node("billing_agent", billing_agent_node)
    graph.add_node("telemetry_agent", telemetry_agent_node)
    graph.add_node("general_agent", general_agent_node)

    # --- Entry point ---
    graph.set_entry_point("router")

    # --- Conditional edges from router ---
    graph.add_conditional_edges(
        "router",
        route_after_router,
        {
            "billing_agent": "billing_agent",
            "telemetry_agent": "telemetry_agent",
            "general_agent": "general_agent",
        },
    )

    # --- All sub-agents terminate for now ---
    graph.add_edge("billing_agent", END)
    graph.add_edge("telemetry_agent", END)
    graph.add_edge("general_agent", END)

    return graph.compile()


def run_support_graph(
    message: str,
    gathered_context: dict[str, Any] | None = None,
) -> AgentState:
    """Run the support graph with a single human message."""
    graph = build_support_graph()
    initial_state = AgentState(
        messages=[HumanMessage(content=message)],
        gathered_context=gathered_context or {},
    )
    return coerce_agent_state(graph.invoke(initial_state))

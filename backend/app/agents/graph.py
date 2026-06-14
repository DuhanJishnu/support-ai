"""Core LangGraph workflow for the support agent system."""

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, StateGraph

from app.agents.state import AgentState, coerce_agent_state


def generic_llm_node(state: AgentState | dict[str, Any]) -> AgentState:
    """Initial deterministic node used to prove the graph flow."""
    agent_state = coerce_agent_state(state)
    response = AIMessage(
        content=(
            "Support agent graph initialized. Ready to route the conversation "
            "once specialized agents are connected."
        )
    )

    return agent_state.model_copy(
        update={
            "messages": [*agent_state.messages, response],
            "current_node": "generic_llm",
            "resolution_status": "in_progress",
            "gathered_context": {
                **agent_state.gathered_context,
                "graph": "support_agent_v1",
                "last_node": "generic_llm",
            },
        }
    )


def build_support_graph():
    """Build and compile the initial support-agent LangGraph."""
    graph = StateGraph(AgentState)
    graph.add_node("generic_llm", generic_llm_node)
    graph.set_entry_point("generic_llm")
    graph.add_edge("generic_llm", END)
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

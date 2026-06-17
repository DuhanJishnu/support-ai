"""Agent nodes for billing, telemetry, and general support queries."""

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import structlog
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.state import AgentState, coerce_agent_state
from app.api import mcp_tools

logger = structlog.get_logger()

BILLING_TOOL_NAME = "verify_transaction_status"
TELEMETRY_TOOL_NAME = "get_ride_route_deviation"


def _latest_human_text(agent_state: AgentState) -> str:
    """Return the most recent human message content as text."""
    human_messages = [m for m in agent_state.messages if isinstance(m, HumanMessage)]
    if not human_messages:
        return ""
    return str(human_messages[-1].content)


def _extract_identifier(
    text: str,
    explicit_value: Any,
    key: str,
    fallback: str,
) -> str:
    """Resolve a tool identifier from context, message text, or a stable fallback."""
    if explicit_value:
        return str(explicit_value)

    patterns = [
        rf"{key}\s*[:=#-]?\s*([A-Za-z0-9_-]+)",
        (
            rf"\b({'txn' if key == 'transaction_id' else 'ride'})"
            r"\s*[:=#-]?\s*([A-Za-z0-9_-]+)"
        ),
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(match.lastindex or 1)

    return fallback


def _run_async_tool(coro: Any) -> Any:
    """Run an async MCP call from sync LangGraph nodes, including API event loops."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(coro)).result()


def _invoke_mcp_tool(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Invoke a discovered MCP tool through the global client manager."""
    client = mcp_tools._mcp_client
    if client is None or not client.is_initialized():
        raise RuntimeError("MCP client is not initialized")
    if client.get_tool(tool_name) is None:
        raise ValueError(f"Tool '{tool_name}' not found in registry")
    return _run_async_tool(client.invoke_tool(tool_name, tool_input))


def _tool_agent_node(
    *,
    label: str,
    node_name: str,
    tool_name: str,
    input_key: str,
    fallback_id: str,
    state: AgentState | dict[str, Any],
) -> AgentState:
    """Execute one MCP tool and inject the result into the agent state."""
    agent_state = coerce_agent_state(state)
    intent = agent_state.gathered_context.get("intent", "GENERAL")
    urgency = agent_state.gathered_context.get("urgency", 1)
    latest_text = _latest_human_text(agent_state)
    identifier = _extract_identifier(
        latest_text,
        agent_state.gathered_context.get(input_key),
        input_key,
        fallback_id,
    )
    tool_input = {input_key: identifier}

    logger.info(
        f"{label}: invoking MCP tool",
        intent=intent,
        urgency=urgency,
        tool_name=tool_name,
        tool_input=tool_input,
    )

    tool_call = {
        "node": node_name,
        "tool_name": tool_name,
        "input": tool_input,
        "status": "pending",
    }
    context_key = "billing" if node_name == "billing_agent" else "telemetry"

    try:
        tool_result = _invoke_mcp_tool(tool_name, tool_input)
        tool_call["status"] = "succeeded"
        logger.info(f"{label}: MCP tool completed", tool_name=tool_name)
        response_text = (
            f"[{label}] I checked `{tool_name}` for `{identifier}` and added the "
            "tool result to the support context for the next decision step."
        )
    except Exception as exc:
        tool_result = {"error": str(exc)}
        tool_call["status"] = "failed"
        logger.warning(
            f"{label}: MCP tool unavailable",
            tool_name=tool_name,
            error=str(exc),
        )
        response_text = (
            f"[{label}] I prepared the `{tool_name}` lookup for `{identifier}`, "
            "but the MCP tool was not available. The request is ready to retry "
            "once tool discovery is healthy."
        )

    response = AIMessage(content=response_text)
    return agent_state.model_copy(
        update={
            "messages": [*agent_state.messages, response],
            "current_node": node_name,
            "resolution_status": "in_progress",
            "gathered_context": {
                **agent_state.gathered_context,
                input_key: identifier,
                "last_node": node_name,
                "last_tool_call": tool_call,
                "tool_calls": [
                    *agent_state.gathered_context.get("tool_calls", []),
                    tool_call,
                ],
                context_key: {
                    "tool": tool_name,
                    "input": tool_input,
                    "result": tool_result,
                },
            },
        }
    )


def billing_agent_node(state: AgentState | dict[str, Any]) -> AgentState:
    """Billing sub-agent that verifies transaction state through MCP."""
    return _tool_agent_node(
        label="BillingAgent",
        node_name="billing_agent",
        tool_name=BILLING_TOOL_NAME,
        input_key="transaction_id",
        fallback_id="txn_mock_latest",
        state=state,
    )


def telemetry_agent_node(state: AgentState | dict[str, Any]) -> AgentState:
    """Telemetry sub-agent that fetches route deviation data through MCP."""
    return _tool_agent_node(
        label="TelemetryAgent",
        node_name="telemetry_agent",
        tool_name=TELEMETRY_TOOL_NAME,
        input_key="ride_id",
        fallback_id="ride_mock_latest",
        state=state,
    )


def generic_llm_node(state: AgentState | dict[str, Any]) -> AgentState:
    """Stub: Generic LLM support sub-agent."""
    agent_state = coerce_agent_state(state)
    intent = agent_state.gathered_context.get("intent", "GENERAL")
    urgency = agent_state.gathered_context.get("urgency", 1)

    logger.info("GenericLLM: handling request", intent=intent, urgency=urgency)

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

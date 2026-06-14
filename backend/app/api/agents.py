"""Agent graph API endpoints."""

from typing import Any

from fastapi import APIRouter
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

from app.agents import run_support_graph

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentRunRequest(BaseModel):
    """Request model for invoking the support agent graph."""

    message: str = Field(..., min_length=1, description="Customer support message")
    gathered_context: dict[str, Any] = Field(default_factory=dict)


class AgentRunResponse(BaseModel):
    """Serialized response from the support agent graph."""

    current_node: str
    resolution_status: str
    gathered_context: dict[str, Any]
    messages: list[dict[str, Any]]


def serialize_message(message: BaseMessage) -> dict[str, Any]:
    """Serialize a LangChain message into a stable API shape."""
    return {
        "type": message.type,
        "content": message.content,
    }


@router.post("/run", response_model=AgentRunResponse)
async def run_agent(request: AgentRunRequest) -> AgentRunResponse:
    """Run the initial support-agent graph."""
    state = run_support_graph(
        message=request.message,
        gathered_context=request.gathered_context,
    )
    return AgentRunResponse(
        current_node=state.current_node,
        resolution_status=state.resolution_status,
        gathered_context=state.gathered_context,
        messages=[serialize_message(message) for message in state.messages],
    )

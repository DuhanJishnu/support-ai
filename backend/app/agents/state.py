"""State schema for the support agent graph."""

from typing import Any, Literal

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, ConfigDict, Field

ResolutionStatus = Literal["received", "in_progress", "resolved", "needs_human"]


class AgentState(BaseModel):
    """Shared state passed between LangGraph support-agent nodes."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    messages: list[BaseMessage] = Field(default_factory=list)
    current_node: str = Field(default="entry")
    gathered_context: dict[str, Any] = Field(default_factory=dict)
    resolution_status: ResolutionStatus = Field(default="received")
    conversation_id: str = Field(default="")
    extracted_entities: dict[str, Any] = Field(default_factory=dict)


def coerce_agent_state(state: AgentState | dict[str, Any]) -> AgentState:
    """Normalize LangGraph outputs into the Pydantic state model."""
    if isinstance(state, AgentState):
        return state
    return AgentState.model_validate(state)

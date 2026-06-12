"""MCP Tools API router for managing external tools."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.mcp_client import MCPClientManager

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

# Global MCP client manager instance
_mcp_client: MCPClientManager | None = None


def get_mcp_client() -> MCPClientManager:
    """Dependency to get the MCP client manager instance."""
    if _mcp_client is None:
        raise HTTPException(
            status_code=503, detail="MCP client not initialized"
        )
    return _mcp_client


class ToolInvokeRequest(BaseModel):
    """Request model for invoking a tool."""

    tool_name: str = Field(..., description="Name of the tool to invoke")
    input: dict = Field(default_factory=dict, description="Tool arguments")


class ToolInfo(BaseModel):
    """Information about an available tool."""

    name: str
    description: str | None = None


@router.get("/health")
async def mcp_health(mcp_client: MCPClientManager = Depends(get_mcp_client)) -> dict:
    """Check MCP client health and initialization status.

    Returns:
        Dictionary with health status and tool count.
    """
    return {
        "status": "ready" if mcp_client.is_initialized() else "initializing",
        "tools_count": len(mcp_client.get_tools()),
    }


@router.get("/tools")
async def list_tools(
    mcp_client: MCPClientManager = Depends(get_mcp_client),
) -> dict:
    """List all available tools discovered from MCP servers.

    Returns:
        Dictionary with tool information.
    """
    tools = mcp_client.get_tools()
    return {
        "tools": [
            {
                "name": name,
                "description": tool.get("description"),
                "input_schema": tool.get("inputSchema"),
            }
            for name, tool in tools.items()
        ],
        "total": len(tools),
    }


@router.post("/invoke")
async def invoke_tool(
    request: ToolInvokeRequest,
    mcp_client: MCPClientManager = Depends(get_mcp_client),
) -> dict:
    """Invoke a specific tool on the appropriate MCP server.

    Args:
        request: Tool invocation request with tool name and input.
        mcp_client: The MCP client manager.

    Returns:
        The result from the tool execution.

    Raises:
        HTTPException: If tool is not found or execution fails.
    """
    try:
        result = await mcp_client.invoke_tool(
            request.tool_name, request.input
        )
        return {"success": True, "result": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


async def initialize_mcp_client(
    telemetry_url: str, billing_url: str, timeout: float = 30.0
) -> MCPClientManager:
    """Initialize the global MCP client manager.

    Args:
        telemetry_url: URL to the telemetry MCP server.
        billing_url: URL to the billing MCP server.
        timeout: Request timeout in seconds.

    Returns:
        Initialized MCPClientManager instance.
    """
    global _mcp_client

    _mcp_client = MCPClientManager(
        telemetry_server_url=telemetry_url,
        billing_server_url=billing_url,
        timeout=timeout,
    )
    await _mcp_client.initialize()
    return _mcp_client

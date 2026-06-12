"""Tests for MCP Client integration."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.mcp_client import MCPClientManager


@pytest.fixture
def mcp_client():
    """Fixture to create an MCP client for testing."""
    return MCPClientManager(
        telemetry_server_url="http://telemetry:8001/sse",
        billing_server_url="http://billing:8002/sse",
        timeout=10.0,
    )


def mcp_context(tools=None, result=None, enter_error=None):
    """Create a mocked FastMCP client async context."""
    client = AsyncMock()
    if enter_error:
        client.__aenter__.side_effect = enter_error
    else:
        client.__aenter__.return_value = client
    client.list_tools.return_value = tools or []
    if result is not None:
        client.call_tool.return_value = result
    return client


class TestMCPClientManager:
    """Test suite for MCPClientManager."""

    def test_initialization(self, mcp_client):
        """Test that MCPClientManager initializes correctly."""
        assert mcp_client.server_urls == [
            "http://telemetry:8001/sse",
            "http://billing:8002/sse",
        ]
        assert mcp_client.telemetry_server_url == "http://telemetry:8001/sse"
        assert mcp_client.billing_server_url == "http://billing:8002/sse"
        assert mcp_client.timeout == 10.0
        assert not mcp_client.is_initialized()
        assert len(mcp_client.get_tools()) == 0

    @pytest.mark.asyncio
    async def test_initialize_success(self, mcp_client):
        """Test successful initialization with mock servers."""
        telemetry_tool = {
            "name": "get_ride_route_deviation",
            "description": "Get ride route deviation",
            "inputSchema": {
                "type": "object",
                "properties": {"ride_id": {"type": "string"}},
            },
        }
        billing_tool = {
            "name": "verify_transaction_status",
            "description": "Verify transaction status",
            "inputSchema": {
                "type": "object",
                "properties": {"transaction_id": {"type": "string"}},
            },
        }

        telemetry_client = mcp_context(tools=[telemetry_tool])
        billing_client = mcp_context(tools=[billing_tool])

        with patch(
            "app.mcp_client.Client",
            side_effect=[telemetry_client, billing_client],
        ) as mock_client:
            await mcp_client.initialize()

            assert mock_client.call_count == 2
            assert mcp_client.is_initialized()
            tools = mcp_client.get_tools()
            assert len(tools) == 2
            assert "get_ride_route_deviation" in tools
            assert "verify_transaction_status" in tools

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, mcp_client):
        """Test that initialize can be called multiple times safely."""
        telemetry_client = mcp_context()
        billing_client = mcp_context()

        with patch(
            "app.mcp_client.Client",
            side_effect=[telemetry_client, billing_client],
        ) as mock_client:
            await mcp_client.initialize()
            initial_state = mcp_client._is_initialized

            await mcp_client.initialize()

            assert mcp_client._is_initialized == initial_state
            assert mock_client.call_count == 2

    @pytest.mark.asyncio
    async def test_discover_tools_from_server(self, mcp_client):
        """Test tool discovery from a specific server."""
        mock_tool = {
            "name": "test_tool",
            "description": "Test tool",
        }
        client = mcp_context(tools=[mock_tool])

        with patch("app.mcp_client.Client", return_value=client):
            await mcp_client._discover_tools_from_server("test", "http://test:8000/sse")

            assert "test_tool" in mcp_client._tools_registry
            assert mcp_client._tools_registry["test_tool"][0] == "http://test:8000/sse"

    @pytest.mark.asyncio
    async def test_discover_tools_server_failure(self, mcp_client):
        """Test handling of server discovery failure."""
        client = mcp_context(enter_error=Exception("Connection failed"))

        with patch("app.mcp_client.Client", return_value=client):
            await mcp_client._discover_tools_from_server("test", "http://test:8000/sse")

            assert len(mcp_client._tools_registry) == 0

    @pytest.mark.asyncio
    async def test_invoke_tool_success(self, mcp_client):
        """Test successful tool invocation."""
        mcp_client._tools_registry["test_tool"] = (
            "http://test:8000/sse",
            {"name": "test_tool"},
        )

        mock_result = {"success": True, "data": "test_data"}
        client = mcp_context(result=SimpleNamespace(data=mock_result))

        with patch("app.mcp_client.Client", return_value=client):
            result = await mcp_client.invoke_tool("test_tool", {"arg": "value"})

            assert result == {"data": mock_result}
            client.call_tool.assert_awaited_once_with("test_tool", {"arg": "value"})

    @pytest.mark.asyncio
    async def test_invoke_tool_not_found(self, mcp_client):
        """Test invocation of non-existent tool."""
        with pytest.raises(ValueError, match="not found in registry"):
            await mcp_client.invoke_tool("non_existent", {})

    @pytest.mark.asyncio
    async def test_invoke_tool_failure(self, mcp_client):
        """Test tool invocation failure."""
        mcp_client._tools_registry["test_tool"] = (
            "http://test:8000/sse",
            {"name": "test_tool"},
        )

        client = mcp_context()
        client.call_tool.side_effect = Exception("Request failed")

        with patch("app.mcp_client.Client", return_value=client):
            with pytest.raises(Exception, match="Request failed"):
                await mcp_client.invoke_tool("test_tool", {})

    def test_get_tools(self, mcp_client):
        """Test getting all registered tools."""
        tool1 = {"name": "tool1", "description": "Tool 1"}
        tool2 = {"name": "tool2", "description": "Tool 2"}

        mcp_client._tools_registry = {
            "tool1": ("http://server1:8000/sse", tool1),
            "tool2": ("http://server2:8000/sse", tool2),
        }

        tools = mcp_client.get_tools()
        assert len(tools) == 2
        assert tools["tool1"] == tool1
        assert tools["tool2"] == tool2

    def test_get_tool_exists(self, mcp_client):
        """Test getting a specific tool that exists."""
        tool = {"name": "test_tool", "description": "Test"}
        mcp_client._tools_registry["test_tool"] = (
            "http://test:8000/sse",
            tool,
        )

        result = mcp_client.get_tool("test_tool")
        assert result == tool

    def test_get_tool_not_found(self, mcp_client):
        """Test getting a tool that doesn't exist."""
        result = mcp_client.get_tool("non_existent")
        assert result is None

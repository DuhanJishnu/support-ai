"""Tests for MCP Client integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.mcp_client import MCPClientManager


@pytest.fixture
def mcp_client():
    """Fixture to create an MCP client for testing."""
    return MCPClientManager(
        telemetry_server_url="http://localhost:8001",
        billing_server_url="http://localhost:8002",
        timeout=10.0,
    )


class TestMCPClientManager:
    """Test suite for MCPClientManager."""

    def test_initialization(self, mcp_client):
        """Test that MCPClientManager initializes correctly."""
        assert mcp_client.telemetry_server_url == "http://localhost:8001"
        assert mcp_client.billing_server_url == "http://localhost:8002"
        assert mcp_client.timeout == 10.0
        assert not mcp_client.is_initialized()
        assert len(mcp_client.get_tools()) == 0

    @pytest.mark.asyncio
    async def test_initialize_success(self, mcp_client):
        """Test successful initialization with mock servers."""
        # Mock telemetry server tools
        telemetry_response = {
            "tools": [
                {
                    "name": "get_ride_route_deviation",
                    "description": "Get ride route deviation",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "ride_id": {"type": "string"}
                        },
                    },
                }
            ]
        }

        # Mock billing server tools
        billing_response = {
            "tools": [
                {
                    "name": "verify_transaction_status",
                    "description": "Verify transaction status",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "transaction_id": {"type": "string"}
                        },
                    },
                }
            ]
        }

        with patch("app.mcp_client.httpx.AsyncClient") as mock_client:
            mock_async_context = AsyncMock()
            mock_response_1 = MagicMock()
            mock_response_1.json.return_value = telemetry_response
            mock_response_1.raise_for_status.return_value = None

            mock_response_2 = MagicMock()
            mock_response_2.json.return_value = billing_response
            mock_response_2.raise_for_status.return_value = None

            mock_async_context.get = AsyncMock(
                side_effect=[mock_response_1, mock_response_2]
            )
            mock_async_context.__aenter__.return_value = mock_async_context

            mock_client.return_value = mock_async_context

            await mcp_client.initialize()

            assert mcp_client.is_initialized()
            tools = mcp_client.get_tools()
            assert len(tools) == 2
            assert "get_ride_route_deviation" in tools
            assert "verify_transaction_status" in tools

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, mcp_client):
        """Test that initialize can be called multiple times safely."""
        with patch("app.mcp_client.httpx.AsyncClient") as mock_client:
            mock_async_context = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {"tools": []}
            mock_response.raise_for_status.return_value = None

            mock_async_context.get = AsyncMock(
                return_value=mock_response
            )
            mock_async_context.__aenter__.return_value = mock_async_context

            mock_client.return_value = mock_async_context

            await mcp_client.initialize()
            initial_state = mcp_client._is_initialized

            # Call initialize again
            await mcp_client.initialize()
            assert mcp_client._is_initialized == initial_state

    @pytest.mark.asyncio
    async def test_discover_tools_from_server(self, mcp_client):
        """Test tool discovery from a specific server."""
        mock_tools = {
            "tools": [
                {
                    "name": "test_tool",
                    "description": "Test tool",
                }
            ]
        }

        with patch("app.mcp_client.httpx.AsyncClient") as mock_client:
            mock_async_context = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = mock_tools
            mock_response.raise_for_status.return_value = None

            mock_async_context.get = AsyncMock(
                return_value=mock_response
            )
            mock_async_context.__aenter__.return_value = mock_async_context

            mock_client.return_value = mock_async_context

            await mcp_client._discover_tools_from_server(
                "test", "http://test:8000"
            )

            assert "test_tool" in mcp_client._tools_registry
            assert mcp_client._tools_registry["test_tool"][0] == "http://test:8000"

    @pytest.mark.asyncio
    async def test_discover_tools_server_failure(self, mcp_client):
        """Test handling of server discovery failure."""
        with patch("app.mcp_client.httpx.AsyncClient") as mock_client:
            mock_async_context = AsyncMock()
            mock_async_context.get = AsyncMock(
                side_effect=Exception("Connection failed")
            )
            mock_async_context.__aenter__.return_value = mock_async_context

            mock_client.return_value = mock_async_context

            # Should not raise, just log warning
            await mcp_client._discover_tools_from_server(
                "test", "http://test:8000"
            )

            assert len(mcp_client._tools_registry) == 0

    @pytest.mark.asyncio
    async def test_invoke_tool_success(self, mcp_client):
        """Test successful tool invocation."""
        # Setup tool in registry
        mcp_client._tools_registry["test_tool"] = (
            "http://test:8000",
            {"name": "test_tool"},
        )

        mock_result = {"success": True, "data": "test_data"}

        with patch("app.mcp_client.httpx.AsyncClient") as mock_client:
            mock_async_context = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = mock_result
            mock_response.raise_for_status.return_value = None

            mock_async_context.post = AsyncMock(
                return_value=mock_response
            )
            mock_async_context.__aenter__.return_value = mock_async_context

            mock_client.return_value = mock_async_context

            result = await mcp_client.invoke_tool(
                "test_tool", {"arg": "value"}
            )

            assert result == mock_result

    @pytest.mark.asyncio
    async def test_invoke_tool_not_found(self, mcp_client):
        """Test invocation of non-existent tool."""
        with pytest.raises(ValueError, match="not found in registry"):
            await mcp_client.invoke_tool("non_existent", {})

    @pytest.mark.asyncio
    async def test_invoke_tool_failure(self, mcp_client):
        """Test tool invocation failure."""
        # Setup tool in registry
        mcp_client._tools_registry["test_tool"] = (
            "http://test:8000",
            {"name": "test_tool"},
        )

        with patch("app.mcp_client.httpx.AsyncClient") as mock_client:
            mock_async_context = AsyncMock()
            mock_async_context.post = AsyncMock(
                side_effect=Exception("Request failed")
            )
            mock_async_context.__aenter__.return_value = mock_async_context

            mock_client.return_value = mock_async_context

            with pytest.raises(Exception, match="Request failed"):
                await mcp_client.invoke_tool("test_tool", {})

    def test_get_tools(self, mcp_client):
        """Test getting all registered tools."""
        tool1 = {"name": "tool1", "description": "Tool 1"}
        tool2 = {"name": "tool2", "description": "Tool 2"}

        mcp_client._tools_registry = {
            "tool1": ("http://server1:8000", tool1),
            "tool2": ("http://server2:8000", tool2),
        }

        tools = mcp_client.get_tools()
        assert len(tools) == 2
        assert tools["tool1"] == tool1
        assert tools["tool2"] == tool2

    def test_get_tool_exists(self, mcp_client):
        """Test getting a specific tool that exists."""
        tool = {"name": "test_tool", "description": "Test"}
        mcp_client._tools_registry["test_tool"] = (
            "http://test:8000", tool
        )

        result = mcp_client.get_tool("test_tool")
        assert result == tool

    def test_get_tool_not_found(self, mcp_client):
        """Test getting a tool that doesn't exist."""
        result = mcp_client.get_tool("non_existent")
        assert result is None

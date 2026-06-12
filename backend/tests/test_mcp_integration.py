"""Integration tests for MCP Tools API."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def app():
    """Create a test FastAPI application."""
    return create_app()


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestMCPToolsAPI:
    """Test suite for MCP Tools API endpoints."""

    def test_list_tools_uninitialized(self):
        """Test listing tools when MCP client is not initialized."""
        from app.api import mcp_tools
        mcp_tools._mcp_client = None

        app = create_app()
        client = TestClient(app)

        response = client.get("/api/mcp/tools")
        assert response.status_code == 503

    def test_list_tools_success(self):
        """Test successfully listing discovered tools."""
        # Mock MCP client
        mock_client = MagicMock()
        mock_client.is_initialized.return_value = True
        mock_client.get_tools.return_value = {
            "get_ride_route_deviation": {
                "name": "get_ride_route_deviation",
                "description": "Get ride route deviation",
                "inputSchema": {
                    "type": "object",
                    "properties": {"ride_id": {"type": "string"}},
                },
            },
            "verify_transaction_status": {
                "name": "verify_transaction_status",
                "description": "Verify transaction status",
                "inputSchema": {
                    "type": "object",
                    "properties": {"transaction_id": {"type": "string"}},
                },
            },
        }

        with patch("app.api.mcp_tools._mcp_client", mock_client):
            app = create_app()
            client = TestClient(app)

            response = client.get("/api/mcp/tools")
            assert response.status_code == 200
            data = response.json()
            assert len(data["tools"]) == 2
            assert data["total"] == 2
            assert any(
                t["name"] == "get_ride_route_deviation" for t in data["tools"]
            )
            assert any(
                t["name"] == "verify_transaction_status" for t in data["tools"]
            )

    def test_mcp_health_not_initialized(self):
        """Test health check when MCP is not initialized."""
        from app.api import mcp_tools
        mcp_tools._mcp_client = None

        app = create_app()
        client = TestClient(app)

        response = client.get("/api/mcp/health")
        assert response.status_code == 503

    def test_mcp_health_initialized(self):
        """Test health check when MCP is initialized."""
        mock_client = MagicMock()
        mock_client.is_initialized.return_value = True
        mock_client.get_tools.return_value = {"tool1": {}, "tool2": {}}

        with patch("app.api.mcp_tools._mcp_client", mock_client):
            app = create_app()
            client = TestClient(app)

            response = client.get("/api/mcp/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
            assert data["tools_count"] == 2

    def test_invoke_tool_not_found(self):
        """Test invoking a tool that doesn't exist."""
        mock_client = MagicMock()
        mock_client.invoke_tool.side_effect = ValueError(
            "Tool 'invalid_tool' not found in registry"
        )

        with patch("app.api.mcp_tools._mcp_client", mock_client):
            app = create_app()
            client = TestClient(app)

            response = client.post(
                "/api/mcp/invoke",
                json={
                    "tool_name": "invalid_tool",
                    "input": {},
                },
            )
            assert response.status_code == 404

    def test_invoke_tool_internal_error(self):
        """Test handling of internal error during tool invocation."""
        mock_client = MagicMock()
        mock_client.invoke_tool.side_effect = Exception(
            "Server connection failed"
        )

        with patch("app.api.mcp_tools._mcp_client", mock_client):
            app = create_app()
            client = TestClient(app)

            response = client.post(
                "/api/mcp/invoke",
                json={
                    "tool_name": "test_tool",
                    "input": {},
                },
            )
            assert response.status_code == 500

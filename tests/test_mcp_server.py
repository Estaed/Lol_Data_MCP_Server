"""
Tests for the MCP Server implementation (Phase 1).
"""
import asyncio
from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

# Add project root to path to allow absolute imports
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from mcp_server.server import MCPServer
from mcp_server.mcp_handler import MCPHandler
from mcp_server.tools import ToolRegistry, GetChampionDataTool

# Fixtures

@pytest.fixture
def handler() -> MCPHandler:
    """Provides a fresh MCPHandler instance for each test."""
    return MCPHandler()

@pytest.fixture
def client() -> TestClient:
    """Provides a FastAPI TestClient for the MCPServer."""
    server = MCPServer()
    return TestClient(server.app)

# Tests for MCPHandler

@pytest.mark.asyncio
async def test_handler_initialize(handler: MCPHandler):
    """Test the handler's initialize response."""
    await handler.initialize()
    message = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": "1",
        "params": {"clientInfo": {"name": "test-client"}}
    }
    response = await handler.handle_message(message)
    
    assert response is not None
    assert response["id"] == "1"
    assert response["result"]["serverInfo"]["name"] == "lol-data-mcp-server"

@pytest.mark.asyncio
async def test_handler_list_tools(handler: MCPHandler):
    """Test the tools/list functionality."""
    await handler.initialize()
    message = {"jsonrpc": "2.0", "method": "tools/list", "id": "2"}
    
    response = await handler.handle_message(message)
    
    assert response is not None
    assert response["id"] == "2"
    assert "tools" in response["result"]
    
    # Check for both basic and data tools
    tool_names = [tool['name'] for tool in response['result']['tools']]
    assert "ping" in tool_names
    assert "get_champion_data" in tool_names

@pytest.mark.asyncio
async def test_handler_call_tool_success(handler: MCPHandler):
    """Test successfully calling a registered tool."""
    await handler.initialize()
    
    # Mock the tool's execute method to return a predictable result
    mock_tool = AsyncMock()
    mock_tool.execute.return_value = {"champion": "Taric", "data": "some_data"}
    
    with patch.object(handler.tool_registry, 'get_tool', return_value=mock_tool):
        message = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": "3",
            "params": {"name": "get_champion_data", "arguments": {"champion": "Taric"}}
        }
        response = await handler.handle_message(message)
        
        assert response is not None
        assert response["id"] == "3"
        assert "error" not in response
        mock_tool.execute.assert_called_once_with({"champion": "Taric"})

@pytest.mark.asyncio
async def test_handler_call_tool_not_found(handler: MCPHandler):
    """Test calling a tool that does not exist."""
    await handler.initialize()
    message = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": "4",
        "params": {"name": "non_existent_tool", "arguments": {}}
    }
    response = await handler.handle_message(message)
    
    assert response is not None
    assert response["id"] == "4"
    assert response["error"]["code"] == -32602 # Method not found
    assert "Tool not found" in response["error"]["message"]

# Tests for Server (Integration)

def test_health_check_endpoint(client: TestClient):
    """Test the /health endpoint."""
    # Need to run startup event to initialize handler
    with patch.object(MCPHandler, "is_healthy", new_callable=AsyncMock) as mock_healthy:
        mock_healthy.return_value = True
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

def test_websocket_connection(client: TestClient):
    """Test establishing a WebSocket connection and sending a message."""
    with client.websocket_connect("/mcp") as websocket:
        # Send initialize message
        init_message = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": "ws-1",
            "params": {"clientInfo": {"name": "ws-test-client"}}
        }
        websocket.send_json(init_message)
        
        # Receive response
        response = websocket.receive_json()
        assert response["id"] == "ws-1"
        assert response["result"]["serverInfo"]["name"] == "lol-data-mcp-server" 
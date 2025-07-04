"""
Tests for the MCP Server implementation (Phase 1).
"""
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

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

# Configure test timeout
pytestmark = pytest.mark.timeout(30)  # 30 second timeout for all tests

# Fixtures

@pytest.fixture
async def handler() -> MCPHandler:
    """Provides a fresh MCPHandler instance for each test with proper cleanup."""
    # Mock external dependencies to prevent network calls
    with patch('src.services.champion_service.ChampionService') as mock_service:
        mock_service.return_value = MagicMock()
        handler = MCPHandler()
        yield handler
        # Explicit cleanup
        await handler.cleanup()

@pytest.fixture
def client() -> TestClient:
    """Provides a FastAPI TestClient for the MCPServer with mocked dependencies."""
    # Mock all external dependencies
    with patch('src.services.champion_service.ChampionService') as mock_service, \
         patch('src.data_sources.scrapers.wiki_scraper.WikiScraper') as mock_scraper:
        
        mock_service.return_value = MagicMock()
        mock_scraper.return_value = MagicMock()
        
        server = MCPServer()
        client = TestClient(server.app)
        yield client
        # TestClient handles its own cleanup

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

@pytest.mark.timeout(10)  # Specific timeout for this test
def test_websocket_connection():
    """Test establishing a WebSocket connection and sending a message."""
    # Create a mock MCP handler
    mock_handler = AsyncMock()
    mock_handler.handle_message.return_value = {
        "jsonrpc": "2.0",
        "id": "ws-1",
        "result": {
            "serverInfo": {"name": "lol-data-mcp-server"},
            "protocolVersion": "2024-11-05",
            "capabilities": {}
        }
    }
    mock_handler.initialize.return_value = None
    mock_handler.cleanup.return_value = None
    mock_handler.is_healthy.return_value = True
    
    # Mock the entire lifespan and server setup
    with patch('src.mcp_server.server.MCPHandler', return_value=mock_handler):
        server = MCPServer()
        
        # Manually set the app state to simulate lifespan
        server.app.state.mcp_handler = mock_handler
        
        client = TestClient(server.app)
        
        try:
            with client.websocket_connect("/mcp") as websocket:
                # Send initialize message
                init_message = {
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "id": "ws-1",
                    "params": {"clientInfo": {"name": "ws-test-client"}}
                }
                websocket.send_json(init_message)
                
                # Receive response with timeout
                response = websocket.receive_json()
                assert response["id"] == "ws-1"
                assert response["result"]["serverInfo"]["name"] == "lol-data-mcp-server"
                
                # Explicitly close the WebSocket
                websocket.close()
                
        except Exception as e:
            # Log any errors for debugging
            print(f"WebSocket test error: {e}")
            raise 
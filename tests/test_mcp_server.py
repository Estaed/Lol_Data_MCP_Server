"""
Tests for MCP Server implementation.

This module tests the basic MCP server functionality including
initialization, health checks, and basic message handling.
"""

import pytest
import pytest_asyncio
import asyncio
import json
from unittest.mock import AsyncMock, patch

from src.mcp_server.server import MCPServer
from src.mcp_server.mcp_handler import MCPHandler


class TestMCPHandler:
    """Test the MCP message handler."""
    
    @pytest_asyncio.fixture
    async def handler(self):
        """Create and initialize an MCP handler for testing."""
        handler = MCPHandler()
        await handler.initialize()
        return handler
    
    @pytest.mark.asyncio
    async def test_initialization(self, handler):
        """Test handler initialization."""
        assert handler.initialized is True
        assert len(handler.tools) > 0
        assert "ping" in handler.tools
        assert "server_info" in handler.tools
    
    @pytest.mark.asyncio
    async def test_health_check(self, handler):
        """Test health check functionality."""
        assert await handler.is_healthy() is True
    
    @pytest.mark.asyncio
    async def test_initialize_message(self, handler):
        """Test MCP initialize message handling."""
        message = {
            "jsonrpc": "2.0",
            "id": "test-1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        response = await handler.handle_message(message)
        
        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "test-1"
        assert "result" in response
        assert response["result"]["protocolVersion"] == "2024-11-05"
        assert "capabilities" in response["result"]
        assert "serverInfo" in response["result"]
    
    @pytest.mark.asyncio
    async def test_list_tools(self, handler):
        """Test tools/list message handling."""
        message = {
            "jsonrpc": "2.0",
            "id": "test-2",
            "method": "tools/list",
            "params": {}
        }
        
        response = await handler.handle_message(message)
        
        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "test-2"
        assert "result" in response
        assert "tools" in response["result"]
        assert len(response["result"]["tools"]) >= 2  # ping and server_info
        
        # Check tool structure
        tools = response["result"]["tools"]
        tool_names = [tool["name"] for tool in tools]
        assert "ping" in tool_names
        assert "server_info" in tool_names
    
    @pytest.mark.asyncio
    async def test_call_ping_tool(self, handler):
        """Test calling the ping tool."""
        message = {
            "jsonrpc": "2.0",
            "id": "test-3",
            "method": "tools/call",
            "params": {
                "name": "ping",
                "arguments": {
                    "message": "test message"
                }
            }
        }
        
        response = await handler.handle_message(message)
        
        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "test-3"
        assert "result" in response
        assert "content" in response["result"]
        assert len(response["result"]["content"]) > 0
        assert "pong: test message" in response["result"]["content"][0]["text"]
    
    @pytest.mark.asyncio
    async def test_call_server_info_tool(self, handler):
        """Test calling the server_info tool."""
        message = {
            "jsonrpc": "2.0",
            "id": "test-4",
            "method": "tools/call",
            "params": {
                "name": "server_info",
                "arguments": {}
            }
        }
        
        response = await handler.handle_message(message)
        
        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "test-4"
        assert "result" in response
    
    @pytest.mark.asyncio
    async def test_call_nonexistent_tool(self, handler):
        """Test calling a tool that doesn't exist."""
        message = {
            "jsonrpc": "2.0",
            "id": "test-5",
            "method": "tools/call",
            "params": {
                "name": "nonexistent_tool",
                "arguments": {}
            }
        }
        
        response = await handler.handle_message(message)
        
        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "test-5"
        assert "error" in response
        assert response["error"]["code"] == -32602
    
    @pytest.mark.asyncio
    async def test_unknown_method(self, handler):
        """Test handling unknown method."""
        message = {
            "jsonrpc": "2.0",
            "id": "test-6",
            "method": "unknown/method",
            "params": {}
        }
        
        response = await handler.handle_message(message)
        
        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "test-6"
        assert "error" in response
        assert response["error"]["code"] == -32601


class TestMCPServer:
    """Test the main MCP server class."""
    
    def test_server_initialization(self):
        """Test server initialization."""
        server = MCPServer(host="localhost", port=8000)
        
        assert server.host == "localhost"
        assert server.port == 8000
        assert server.app is not None
        assert server.app.title == "LoL Data MCP Server"
    
    @pytest.mark.asyncio
    async def test_server_startup_shutdown(self):
        """Test server startup and shutdown process."""
        server = MCPServer()
        
        # Mock uvicorn server to avoid actually starting it
        with patch('src.mcp_server.server.uvicorn.Server') as mock_server:
            mock_instance = AsyncMock()
            mock_server.return_value = mock_instance
            
            # Test server start
            await server.start()
            
            # Verify server was configured and started
            mock_server.assert_called_once()
            mock_instance.serve.assert_called_once()


@pytest.mark.asyncio
async def test_integration_server_health():
    """Integration test for server health endpoint."""
    from fastapi.testclient import TestClient
    from src.mcp_server.server import MCPServer
    
    server = MCPServer()
    client = TestClient(server.app)
    
    # Test health endpoint
    response = client.get("/health")
    
    # Should return 503 initially as handler may not be fully initialized
    assert response.status_code in [200, 503] 
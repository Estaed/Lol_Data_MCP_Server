"""
Basic MCP Server Usage Example

This example demonstrates how to interact with the LoL Data MCP Server
using subprocess communication (stdio protocol) and test the available tools.

Since our MCP server uses stdio protocol for Cursor integration, this example
shows how to programmatically test and interact with the server.
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path


class MCPStdioClient:
    """Simple client to test MCP server via stdio."""
    
    def __init__(self, server_script_path: str):
        self.server_script_path = server_script_path
        self.process = None
    
    async def start(self):
        """Start the MCP server process."""
        self.process = await asyncio.create_subprocess_exec(
            sys.executable, self.server_script_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
    async def send_message(self, message: dict) -> dict:
        """Send a message to the MCP server and get response."""
        if not self.process or not self.process.stdin or not self.process.stdout:
            raise RuntimeError("Server not started or streams not available")
            
        message_json = json.dumps(message) + "\n"
        self.process.stdin.write(message_json.encode())
        await self.process.stdin.drain()
        
        # Read response
        response_line = await self.process.stdout.readline()
        return json.loads(response_line.decode().strip())
    
    async def close(self):
        """Close the connection to the server."""
        if self.process and self.process.stdin:
            self.process.stdin.close()
            await self.process.wait()


async def test_mcp_server():
    """Test the MCP server functionality."""
    # Path to our stdio server
    server_path = str(Path(__file__).parent.parent.parent / "src" / "mcp_server" / "stdio_server.py")
    
    client = MCPStdioClient(server_path)
    
    try:
        print("🚀 Starting MCP Server...")
        await client.start()
        
        # Initialize the server
        print("📡 Initializing MCP connection...")
        init_response = await client.send_message({
            "jsonrpc": "2.0",
            "id": "init",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        })
        print("✅ Server initialized:", init_response.get("result", {}).get("serverInfo"))
        
        # Send initialized notification
        await client.send_message({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        })
        
        # List available tools
        print("\n🔧 Listing available tools...")
        tools_response = await client.send_message({
            "jsonrpc": "2.0",
            "id": "list_tools",
            "method": "tools/list",
            "params": {}
        })
        
        tools = tools_response.get("result", {}).get("tools", [])
        print(f"✅ Found {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")
        
        # Test ping tool
        print("\n🏓 Testing ping tool...")
        ping_response = await client.send_message({
            "jsonrpc": "2.0",
            "id": "ping_test",
            "method": "tools/call",
            "params": {
                "name": "ping",
                "arguments": {"message": "Hello from test client!"}
            }
        })
        print("✅ Ping response:", ping_response.get("result", {}).get("content", [{}])[0].get("text"))
        
        # Test get_champion_data for Taric
        print("\n⚔️ Getting Taric champion data...")
        taric_response = await client.send_message({
            "jsonrpc": "2.0",
            "id": "taric_test",
            "method": "tools/call",
            "params": {
                "name": "get_champion_data",
                "arguments": {
                    "champion": "Taric",
                    "include": ["stats", "abilities"]
                }
            }
        })
        
        if "error" in taric_response:
            print("❌ Error getting Taric data:", taric_response["error"])
        else:
            print("✅ Taric data retrieved successfully!")
            # Parse the response content
            content = taric_response.get("result", {}).get("content", [{}])[0].get("text", "")
            if content:
                try:
                    taric_data = json.loads(content)
                    print(f"  - Name: {taric_data.get('name', 'Unknown')}")
                    print(f"  - Title: {taric_data.get('title', 'Unknown')}")
                    print(f"  - Role: {taric_data.get('role', 'Unknown')}")
                    stats = taric_data.get('stats', {})
                    if stats:
                        print(f"  - Health: {stats.get('health', 'Unknown')}")
                        print(f"  - Attack Damage: {stats.get('attack_damage', 'Unknown')}")
                except json.JSONDecodeError:
                    print(f"  - Raw response: {content[:200]}...")
        
        # Test server info
        print("\n📊 Getting server information...")
        info_response = await client.send_message({
            "jsonrpc": "2.0",
            "id": "info_test",
            "method": "tools/call",
            "params": {
                "name": "server_info",
                "arguments": {}
            }
        })
        print("✅ Server info:", info_response.get("result", {}).get("content", [{}])[0].get("text"))
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
    finally:
        print("\n🔄 Closing connection...")
        await client.close()
        print("✅ Test completed!")


async def main():
    """Main function to run the MCP server test."""
    print("=" * 60)
    print("🎮 LoL Data MCP Server - Client Usage Example")
    print("=" * 60)
    
    await test_mcp_server()


if __name__ == "__main__":
    asyncio.run(main())

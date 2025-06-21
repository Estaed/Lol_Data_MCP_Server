"""
Basic MCP Client Usage Example

This example demonstrates how to connect to the LoL Data MCP Server
and make basic requests for champion and item data.
"""

import asyncio
import json
from mcp_client import MCPClient


async def main():
    # Connect to MCP server
    client = MCPClient("ws://localhost:8000/mcp")
    await client.connect()

    try:
        # Get Taric's champion data
        taric_data = await client.call_tool(
            "get_champion_data",
            {"champion": "Taric", "include": ["stats", "abilities"]},
        )
        print("Taric Data:", json.dumps(taric_data, indent=2))

        # Get Taric's Q ability details
        q_ability = await client.call_tool(
            "get_ability_details", {"champion": "Taric", "ability": "Q", "level": 5}
        )
        print("Taric Q at Level 5:", json.dumps(q_ability, indent=2))

        # Search for support champions
        supports = await client.call_tool(
            "search_champions", {"role": "support", "limit": 5}
        )
        print("Support Champions:", json.dumps(supports, indent=2))

    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

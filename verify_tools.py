#!/usr/bin/env python3
"""
Simple verification script for MCP tools
"""

import asyncio
import sys
from src.tools import tool_registry


async def main():
    """Run basic verification tests"""
    try:
        print("🔍 Starting MCP Tools Verification...")
        print(f"Python version: {sys.version}")

        # Test 1: Tool Registry
        print("\n1. Testing Tool Registry...")
        tool_names = tool_registry.get_tool_names()
        print(f"   ✅ Tools loaded: {len(tool_names)}")
        print(f"   ✅ Tool names: {tool_names}")

        expected_tools = [
            "get_champion_data",
            "get_ability_details",
            "get_item_data",
            "search_champions",
            "get_meta_builds",
        ]
        if all(tool in tool_names for tool in expected_tools):
            print("   ✅ All expected tools present")
        else:
            print("   ❌ Missing tools")
            return False

        # Test 2: Schema Validation
        print("\n2. Testing Tool Schemas...")
        schemas = tool_registry.list_tools()
        if len(schemas) == 5:
            print(f"   ✅ All 5 tool schemas available")
        else:
            print(f"   ❌ Expected 5 schemas, got {len(schemas)}")
            return False

        # Test 3: Tool Execution
        print("\n3. Testing Tool Execution...")

        # Test get_champion_data
        result = await tool_registry.execute_tool(
            "get_champion_data", {"champion": "Taric"}
        )
        if result["champion"] == "Taric":
            print("   ✅ get_champion_data works")
        else:
            print("   ❌ get_champion_data failed")
            return False

        # Test get_ability_details
        result = await tool_registry.execute_tool(
            "get_ability_details", {"champion": "Taric", "ability": "Q"}
        )
        if result["champion"] == "Taric" and result["ability"] == "Q":
            print("   ✅ get_ability_details works")
        else:
            print("   ❌ get_ability_details failed")
            return False

        # Test get_item_data
        result = await tool_registry.execute_tool(
            "get_item_data", {"item": "Blade of the Ruined King"}
        )
        if result["item"] == "Blade of the Ruined King":
            print("   ✅ get_item_data works")
        else:
            print("   ❌ get_item_data failed")
            return False

        # Test search_champions
        result = await tool_registry.execute_tool(
            "search_champions", {"query": "support"}
        )
        if "query" in result and result["query"] == "support":
            print("   ✅ search_champions works")
        else:
            print("   ❌ search_champions failed")
            return False

        # Test get_meta_builds
        result = await tool_registry.execute_tool(
            "get_meta_builds", {"champion": "Taric"}
        )
        if result["champion"] == "Taric":
            print("   ✅ get_meta_builds works")
        else:
            print("   ❌ get_meta_builds failed")
            return False

        # Test 4: Error Handling
        print("\n4. Testing Error Handling...")
        try:
            await tool_registry.execute_tool("invalid_tool", {})
            print("   ❌ Error handling failed - should have raised exception")
            return False
        except ValueError as e:
            if "not found" in str(e):
                print("   ✅ Error handling works")
            else:
                print(f"   ❌ Unexpected error: {e}")
                return False

        print("\n🎉 ALL TESTS PASSED! MCP Tools are working correctly! ✅")
        return True

    except Exception as e:
        print(f"\n❌ TESTS FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

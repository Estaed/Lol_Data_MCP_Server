"""
Tests for MCP Tools

Test suite to verify all MCP tools validate inputs and return structured outputs.
"""

import pytest
import asyncio
from src.tools import (
    tool_registry,
    GetChampionDataTool,
    GetAbilityDetailsTool,
    GetItemDataTool,
    SearchChampionsTool,
    GetMetaBuildsTool,
    GetChampionDataInput,
    GetAbilityDetailsInput,
    AbilityType,
)


class TestToolRegistry:
    """Test the tool registry functionality"""

    def test_tool_registry_initialization(self):
        """Test that all tools are registered correctly"""
        tool_names = tool_registry.get_tool_names()
        expected_tools = [
            "get_champion_data",
            "get_ability_details",
            "get_item_data",
            "search_champions",
            "get_meta_builds",
        ]

        assert len(tool_names) == 5
        assert all(tool in tool_names for tool in expected_tools)

    def test_get_tool(self):
        """Test getting a tool by name"""
        tool = tool_registry.get_tool("get_champion_data")
        assert tool is not None
        assert isinstance(tool, GetChampionDataTool)
        assert tool.name == "get_champion_data"

    def test_list_tools_schemas(self):
        """Test getting all tool schemas"""
        schemas = tool_registry.list_tools()
        assert len(schemas) == 5

        for schema in schemas:
            assert hasattr(schema, "name")
            assert hasattr(schema, "description")
            assert hasattr(schema, "input_schema")


class TestInputValidation:
    """Test input validation for all tools"""

    def test_get_champion_data_input_validation(self):
        """Test champion data input validation"""
        # Valid input
        valid_input = GetChampionDataInput(champion="Taric")
        assert valid_input.champion == "Taric"
        assert valid_input.patch == "current"
        assert valid_input.include == ["stats", "abilities"]

        # Invalid include options
        with pytest.raises(ValueError):
            GetChampionDataInput(champion="Taric", include=["invalid_option"])

    def test_get_ability_details_input_validation(self):
        """Test ability details input validation"""
        # Valid input
        valid_input = GetAbilityDetailsInput(
            champion="Taric", ability=AbilityType.Q, level=10
        )
        assert valid_input.champion == "Taric"
        assert valid_input.ability == AbilityType.Q
        assert valid_input.level == 10

        # Level out of range
        with pytest.raises(ValueError):
            GetAbilityDetailsInput(champion="Taric", ability=AbilityType.Q, level=20)


class TestToolExecution:
    """Test tool execution and output structure"""

    @pytest.mark.asyncio
    async def test_get_champion_data_execution(self):
        """Test champion data tool execution"""
        params = {"champion": "Taric", "include": ["stats", "abilities"]}
        result = await tool_registry.execute_tool("get_champion_data", params)

        # Verify output structure
        assert "champion" in result
        assert "patch" in result
        assert "data_included" in result
        assert result["champion"] == "Taric"
        assert "stats" in result["data_included"]
        assert "abilities" in result["data_included"]

    @pytest.mark.asyncio
    async def test_get_ability_details_execution(self):
        """Test ability details tool execution"""
        params = {"champion": "Taric", "ability": "Q", "level": 10}
        result = await tool_registry.execute_tool("get_ability_details", params)

        # Verify output structure
        assert "champion" in result
        assert "ability" in result
        assert "level" in result
        assert "scaling_included" in result
        assert result["champion"] == "Taric"
        assert result["ability"] == "Q"
        assert result["level"] == 10

    @pytest.mark.asyncio
    async def test_get_item_data_execution(self):
        """Test item data tool execution"""
        params = {"item": "Blade of the Ruined King"}
        result = await tool_registry.execute_tool("get_item_data", params)

        # Verify output structure
        assert "item" in result
        assert "data_included" in result
        assert result["item"] == "Blade of the Ruined King"

    @pytest.mark.asyncio
    async def test_search_champions_execution(self):
        """Test search champions tool execution"""
        params = {"query": "support", "limit": 5}
        result = await tool_registry.execute_tool("search_champions", params)

        # Verify output structure
        assert "query" in result
        assert "filters" in result
        assert "limit" in result
        assert "results" in result
        assert result["query"] == "support"
        assert result["limit"] == 5

    @pytest.mark.asyncio
    async def test_get_meta_builds_execution(self):
        """Test meta builds tool execution"""
        params = {"champion": "Taric", "rank": "diamond+"}
        result = await tool_registry.execute_tool("get_meta_builds", params)

        # Verify output structure
        assert "champion" in result
        assert "rank" in result
        assert "builds" in result
        assert result["champion"] == "Taric"
        assert result["rank"] == "diamond+"


class TestToolSchemas:
    """Test tool schema definitions"""

    def test_get_champion_data_schema(self):
        """Test champion data tool schema"""
        tool = tool_registry.get_tool("get_champion_data")
        schema = tool.get_schema()

        assert schema.name == "get_champion_data"
        assert "champion" in schema.input_schema["required"]
        assert "properties" in schema.input_schema
        assert "champion" in schema.input_schema["properties"]

    def test_get_ability_details_schema(self):
        """Test ability details tool schema"""
        tool = tool_registry.get_tool("get_ability_details")
        schema = tool.get_schema()

        assert schema.name == "get_ability_details"
        assert "champion" in schema.input_schema["required"]
        assert "ability" in schema.input_schema["required"]

        # Check enum values for ability
        ability_enum = schema.input_schema["properties"]["ability"]["enum"]
        assert "Q" in ability_enum
        assert "passive" in ability_enum

    def test_all_tools_have_valid_schemas(self):
        """Test that all tools have valid schema definitions"""
        for tool_name in tool_registry.get_tool_names():
            tool = tool_registry.get_tool(tool_name)
            schema = tool.get_schema()

            # Basic schema validation
            assert hasattr(schema, "name")
            assert hasattr(schema, "description")
            assert hasattr(schema, "input_schema")
            assert isinstance(schema.input_schema, dict)
            assert "type" in schema.input_schema
            assert schema.input_schema["type"] == "object"


class TestErrorHandling:
    """Test error handling for invalid inputs"""

    @pytest.mark.asyncio
    async def test_invalid_tool_name(self):
        """Test calling non-existent tool"""
        with pytest.raises(ValueError, match="Tool 'invalid_tool' not found"):
            await tool_registry.execute_tool("invalid_tool", {})

    @pytest.mark.asyncio
    async def test_missing_required_params(self):
        """Test calling tool with missing required parameters"""
        with pytest.raises(ValueError):
            await tool_registry.execute_tool("get_champion_data", {})


if __name__ == "__main__":
    # Run basic tests if executed directly
    import sys

    print("Running basic tool validation tests...")

    # Test tool registry
    print(f"✓ Tools loaded: {len(tool_registry.get_tool_names())}")
    print(f"✓ Tool names: {tool_registry.get_tool_names()}")

    # Test async functionality
    async def run_basic_tests():
        try:
            # Test champion data
            result = await tool_registry.execute_tool(
                "get_champion_data", {"champion": "Taric"}
            )
            print(f"✓ get_champion_data: {result['champion']}")

            # Test ability details
            result = await tool_registry.execute_tool(
                "get_ability_details", {"champion": "Taric", "ability": "Q"}
            )
            print(f"✓ get_ability_details: {result['champion']} {result['ability']}")

            # Test schema validation
            tool = tool_registry.get_tool("get_champion_data")
            schema = tool.get_schema()
            print(f"✓ Schema validation: {schema.name}")

            print("\nAll basic tests passed! ✅")
            return True

        except Exception as e:
            print(f"❌ Test failed: {e}")
            return False

    # Run the tests
    success = asyncio.run(run_basic_tests())
    sys.exit(0 if success else 1)

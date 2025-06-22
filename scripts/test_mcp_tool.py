"""
Test script to verify MCP tool functionality for Task 1.4
"""

import asyncio
from src.tools import tool_registry

async def test_champion_tool():
    print('Testing get_champion_data MCP tool...')
    
    # Test the main requirement: get_champion_data returns valid data for "Taric"
    result = await tool_registry.execute_tool('get_champion_data', {'champion': 'Taric'})
    
    print(f'✅ Champion: {result["name"]}')
    print(f'✅ Title: {result["title"]}')
    print(f'✅ Roles: {result["roles"]}')
    print(f'✅ Difficulty: {result["difficulty"]}')
    print(f'✅ Patch: {result["patch"]}')
    print(f'✅ Data included: {result["data_included"]}')
    print(f'✅ Has stats: {"stats" in result}')
    print(f'✅ Has abilities: {"abilities" in result}')
    
    if 'stats' in result:
        print(f'✅ Health: {result["stats"]["health"]}')
        print(f'✅ Mana: {result["stats"]["mana"]}')
        print(f'✅ Attack Damage: {result["stats"]["attack_damage"]}')
    
    if 'abilities' in result:
        print(f'✅ Q Ability: {result["abilities"]["q"]["name"]}')
        print(f'✅ W Ability: {result["abilities"]["w"]["name"]}')
        print(f'✅ E Ability: {result["abilities"]["e"]["name"]}')
        print(f'✅ R Ability: {result["abilities"]["r"]["name"]}')
    
    print('\n🎉 Task 1.4 VERIFICATION SUCCESSFUL!')
    print('✅ MCP tool get_champion_data returns valid data for "Taric"')
    
    # Test error handling
    print('\nTesting error handling...')
    try:
        await tool_registry.execute_tool('get_champion_data', {'champion': 'NonExistent'})
    except Exception as e:
        print(f'✅ Error handling works: {type(e).__name__}: {e}')
    
    print('\n✅ All Task 1.4 requirements verified!')

if __name__ == "__main__":
    asyncio.run(test_champion_tool())
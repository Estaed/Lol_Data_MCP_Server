#!/usr/bin/env python3
"""
Test multiple items to ensure broad compatibility
"""

import asyncio
import sys
import os
sys.path.insert(0, 'src')

from data_sources.scrapers.items.item_data_scraper import ItemDataScraper
import json

async def test_multiple_items():
    scraper = ItemDataScraper(
        rate_limit_delay=1.0,
        timeout=30.0,
        max_retries=3,
        enable_cache=False
    )
    
    test_items = [
        'Echoes of Helia',  # Completed item
        'Kindlegem',        # Basic item  
        'Needlessly Large Rod'  # Basic item
    ]
    
    try:
        for item_name in test_items:
            print(f'\n=== TESTING {item_name.upper()} ===')
            
            try:
                result = await scraper.scrape_item_data(item_name, sections=['stats', 'recipe'])
                
                if 'data' in result:
                    data = result['data']
                    item_type = result.get('item_type', 'unknown')
                    print(f'Item type: {item_type}')
                    
                    # Check stats format
                    if 'stats' in data:
                        stats = data["stats"]
                        if 'base_stats' in stats:
                            print(f'Base stats found: {len(stats["base_stats"])} stats')
                        if 'masterwork_stats' in stats:
                            print(f'Masterwork stats found: {len(stats["masterwork_stats"])} stats')
                            # Show one example
                            for key, value in list(stats["masterwork_stats"].items())[:1]:
                                print(f'  Example: {key} = {value}')
                    
                    # Check recipe
                    if 'recipe' in data:
                        recipe = data["recipe"]
                        if 'main_components' in recipe:
                            comp_count = len(recipe["main_components"])
                            print(f'Recipe components: {comp_count}')
                        if 'builds_into' in recipe:
                            builds_count = len(recipe.get("builds_into", []))
                            print(f'Builds into: {builds_count} items')
                            
                    print('SUCCESS: Item processed correctly')
                
            except Exception as e:
                print(f'ERROR with {item_name}: {e}')
                
        print('\n=== MULTIPLE ITEMS TEST COMPLETE ===')
        
    except Exception as e:
        print(f'Overall error: {e}')
        import traceback
        traceback.print_exc()
    finally:
        await scraper.close()

if __name__ == "__main__":
    asyncio.run(test_multiple_items())
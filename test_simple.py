#!/usr/bin/env python3
"""
Simple test script for enhanced ItemDataScraper functionality
"""

import asyncio
import sys
import os
sys.path.insert(0, 'src')

from data_sources.scrapers.items.item_data_scraper import ItemDataScraper
import json

async def test_simple():
    scraper = ItemDataScraper(
        rate_limit_delay=1.0,
        timeout=30.0,
        max_retries=3,
        enable_cache=False
    )
    
    try:
        print('Testing enhanced ItemDataScraper with Echoes of Helia...')
        result = await scraper.scrape_item_data('Echoes of Helia', sections=['stats', 'recipe', 'cost_analysis'])
        
        if 'data' in result:
            data = result['data']
            
            print('\n=== TESTING RESULTS ===')
            
            # Test stats format
            if 'stats' in data:
                print('\nStats format check:')
                stats = data["stats"]
                if 'masterwork_stats' in stats:
                    for stat_name, stat_value in stats['masterwork_stats'].items():
                        print(f'  {stat_name}: {stat_value}')
                        if '(+' in str(stat_value) and ')' in str(stat_value):
                            print('  PASS: Stats show enhanced format with bonus values')
                            break
            
            # Test recipe structure  
            if 'recipe' in data:
                print('\nRecipe structure check:')
                recipe = data["recipe"]
                print(f'  Recipe data: {recipe}')
                if 'main_components' in recipe:
                    print('  PASS: Recipe has hierarchical structure')
            
            # Test enhanced cost analysis
            if 'cost_analysis' in data:
                print('\nCost analysis check:')
                cost_analysis = data["cost_analysis"] 
                print(f'  Cost analysis: {cost_analysis}')
                if 'efficiency_percentage' in cost_analysis:
                    print(f'  PASS: Has efficiency percentage: {cost_analysis["efficiency_percentage"]}%')
                if 'stat_efficiency' in cost_analysis:
                    print('  PASS: Has detailed stat efficiency breakdown')
        
        print('\n=== TEST COMPLETE ===')
        
    except Exception as e:
        print(f'Error testing scraper: {e}')
        import traceback
        traceback.print_exc()
    finally:
        await scraper.close()

if __name__ == "__main__":
    asyncio.run(test_simple())
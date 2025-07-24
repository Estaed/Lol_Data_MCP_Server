#!/usr/bin/env python3
"""
Test script for enhanced ItemDataScraper functionality
"""

import asyncio
import sys
import os
sys.path.insert(0, 'src')

from data_sources.scrapers.items.item_data_scraper import ItemDataScraper
import json

async def test_enhanced_scraper():
    scraper = ItemDataScraper(
        rate_limit_delay=1.0,
        timeout=30.0,
        max_retries=3,
        enable_cache=False  # Disable cache for fresh test
    )
    
    try:
        print('Testing enhanced ItemDataScraper with Echoes of Helia...')
        result = await scraper.scrape_item_data('Echoes of Helia', sections=['stats', 'recipe', 'cost_analysis'])
        
        print('\n=== ENHANCED SCRAPER RESULTS ===')
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Specifically check our enhanced features
        if 'data' in result:
            data = result['data']
            
            print('\n=== TESTING ENHANCED FEATURES ===')
            
            # Test stats format
            if 'stats' in data:
                print(f'\n✓ Stats format: {data["stats"]}')
            
            # Test recipe structure  
            if 'recipe' in data:
                print(f'\n✓ Recipe structure: {data["recipe"]}')
            
            # Test enhanced cost analysis
            if 'cost_analysis' in data:
                print(f'\n✓ Enhanced cost analysis: {data["cost_analysis"]}')
        
    except Exception as e:
        print(f'❌ Error testing enhanced scraper: {e}')
        import traceback
        traceback.print_exc()
    finally:
        await scraper.close()

if __name__ == "__main__":
    asyncio.run(test_enhanced_scraper())
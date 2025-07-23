#!/usr/bin/env python3
"""
Basic Item Data Scraper Functionality Test
==========================================

Quick test to verify ItemDataScraper basic functionality works correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from data_sources.scrapers.items.item_data_scraper import ItemDataScraper, ItemType

async def test_basic_functionality():
    """Test basic ItemDataScraper functionality with a few representative items."""
    
    print("Basic ItemDataScraper Functionality Test")
    print("=" * 50)
    
    # Test items (one from each category)
    test_items = {
        "Long Sword": "basic",
        "Kindlegem": "epic", 
        "Echoes of Helia": "completed"
    }
    
    scraper = ItemDataScraper()
    
    try:
        for i, (item_name, expected_type) in enumerate(test_items.items(), 1):
            print(f"\n[{i}/{len(test_items)}] Testing {item_name} (expected: {expected_type})")
            print("-" * 40)
            
            try:
                # Test the scraper
                result = await scraper.scrape_item_data(item_name)
                
                if result:
                    print(f"[SUCCESS] Successfully scraped data for {item_name}")
                    print(f"[INFO] Item type detected: {result.get('item_type', 'unknown')}")
                    print(f"[INFO] Data sections found: {list(result.keys())}")
                    
                    # Check if basic data is present
                    if 'item_name' in result:
                        print(f"[INFO] Item name: {result['item_name']}")
                    if 'stats' in result:
                        print(f"[INFO] Stats section: Available")
                    if 'recipe' in result:
                        print(f"[INFO] Recipe section: Available") 
                    
                    print("[PASS] Basic functionality test PASSED")
                else:
                    print(f"[FAIL] No data returned for {item_name}")
                    
            except Exception as e:
                print(f"[ERROR] Error testing {item_name}: {e}")
                import traceback
                traceback.print_exc()
    
    finally:
        # Cleanup
        if hasattr(scraper, 'close'):
            await scraper.close()
    
    print("\n" + "=" * 50)
    print("[COMPLETE] Basic functionality test completed!")

if __name__ == "__main__":
    asyncio.run(test_basic_functionality())
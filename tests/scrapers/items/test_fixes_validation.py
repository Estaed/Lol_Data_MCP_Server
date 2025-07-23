#!/usr/bin/env python3
"""
Test Critical Fixes Validation
=============================

Test the critical fixes identified by Gemini CLI analysis:
1. URL normalization for special characters
2. Selenium URL passing
3. Integration robustness
"""

import asyncio
import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from data_sources.scrapers.items.item_data_scraper import ItemDataScraper

async def test_critical_fixes():
    """Test the critical fixes for URL normalization and Selenium integration."""
    
    print("Critical Fixes Validation Test")
    print("=" * 50)
    
    # Test items with special characters that would break the old URL generation
    test_items = [
        "Doran's Blade",     # Has apostrophe - critical test case
        "Doran's Ring",      # Has apostrophe 
        "Doran's Shield",    # Has apostrophe
        "Long Sword",        # Space - should work with both old and new
        "Echoes of Helia"    # Complex name with spaces
    ]
    
    scraper = ItemDataScraper()
    
    try:
        for i, item_name in enumerate(test_items, 1):
            print(f"\n[{i}/{len(test_items)}] Testing {item_name}")
            print("-" * 40)
            
            # Test URL normalization
            normalized_url = scraper._build_item_url(item_name)
            print(f"[URL] Generated URL: {normalized_url}")
            
            # Test if URL handles special characters correctly
            if "'" in item_name:
                if "%27" in normalized_url:
                    print("[URL] SUCCESS: Apostrophe correctly encoded as %27")
                else:
                    print("[URL] FAIL: Apostrophe not properly encoded")
            
            if " " in item_name:
                if "_" in normalized_url and " " not in normalized_url:
                    print("[URL] SUCCESS: Spaces correctly replaced with underscores")
                else:
                    print("[URL] FAIL: Spaces not properly handled")
            
            try:
                # Test basic scraping functionality
                result = await scraper.scrape_item_data(item_name)
                
                if result:
                    print(f"[SCRAPE] SUCCESS: Data extracted for {item_name}")
                    print(f"[SCRAPE] Type detected: {result.get('item_type', 'unknown')}")
                    
                    # Check if URL fixes prevent errors
                    if result.get('item_name'):
                        print("[SCRAPE] SUCCESS: Item name correctly extracted")
                    
                else:
                    print(f"[SCRAPE] INFO: No data returned (might be normal for some items)")
                    
            except Exception as e:
                print(f"[SCRAPE] ERROR: {e}")
                # Check if it's a URL-related error
                if "404" in str(e) or "Not Found" in str(e):
                    print("[SCRAPE] This might be a URL normalization issue")
                
    finally:
        if hasattr(scraper, 'close'):
            await scraper.close()
    
    print("\n" + "=" * 50)
    print("[COMPLETE] Critical fixes validation completed!")

async def test_url_normalization_directly():
    """Test URL normalization method directly."""
    print("\nDirect URL Normalization Test")
    print("=" * 40)
    
    scraper = ItemDataScraper()
    
    test_cases = [
        ("Doran's Blade", "Doran%27s_Blade"),
        ("echoes of helia", "Echoes_Of_Helia"), 
        ("Long Sword", "Long_Sword"),
        ("Kai'Sa's Second Skin", "Kai%27sa%27s_Second_Skin"),
        ("B. F. Sword", "B._F._Sword")
    ]
    
    for original, expected in test_cases:
        normalized = scraper.normalize_item_name(original)
        url = scraper._build_item_url(original)
        
        print(f"Original: '{original}'")
        print(f"Normalized: '{normalized}'")
        print(f"Full URL: {url}")
        print(f"Expected pattern: '{expected}'")
        
        if expected.lower() in normalized.lower():
            print("[PASS] Normalization correct")
        else:
            print("[FAIL] Normalization incorrect")
        print("-" * 20)

if __name__ == "__main__":
    asyncio.run(test_critical_fixes())
    asyncio.run(test_url_normalization_directly())
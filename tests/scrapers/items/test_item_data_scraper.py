#!/usr/bin/env python3
"""
Comprehensive Item Data Scraper Testing
=====================================

This script tests the ItemDataScraper functionality across different types of League of Legends items
to ensure robust implementation and proper differentiated extraction.

Usage:
    python tests/scrapers/items/test_item_data_scraper.py

Features:
- Tests completed items (legendary/mythic)
- Tests basic items 
- Tests epic items
- Tests all extraction sections
- Comprehensive error reporting
- Progress tracking
- Summary statistics
"""

import asyncio
import sys
import time
from pathlib import Path
from typing import Dict, List, Any
import json

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from data_sources.scrapers.items.item_data_scraper import ItemDataScraper, ItemType

# Test items representing different categories
TEST_ITEMS = {
    'completed': [
        "Echoes of Helia",      # Legendary support item
        "Eclipse",              # Legendary assassin item  
        "Sunfire Aegis",        # Legendary tank item
        "Kraken Slayer",        # Legendary marksman mythic
        "Liandry's Anguish",    # Legendary mage mythic
        "Goredrinker",          # Legendary fighter mythic
        "Locket of the Iron Solari",  # Legendary support mythic
        "Chemtank Purifier",    # Legendary tank mythic
        "Night Harvester",      # Legendary mage mythic
        "Duskblade of Draktharr"  # Legendary assassin mythic
    ],
    'epic': [
        "Kindlegem",            # Epic health/cdr component
        "Needlessly Large Rod", # Epic AP component
        "Vampiric Scepter",     # Epic lifesteal component  
        "Chain Vest",           # Epic armor component
        "Negatron Cloak",       # Epic MR component
        "Recurve Bow",          # Epic attack speed component
        "Sheen",                # Epic mana/cdr component
        "Hexdrinker",           # Epic AD/MR component
        "Phage",                # Epic health/AD component
        "Aether Wisp"           # Epic AP/MS component
    ],
    'basic': [
        "Long Sword",           # Basic AD component
        "Amplifying Tome",      # Basic AP component
        "Ruby Crystal",         # Basic health component
        "Sapphire Crystal",     # Basic mana component
        "Cloth Armor",          # Basic armor component
        "Null-Magic Mantle",    # Basic MR component
        "Dagger",               # Basic attack speed component
        "Boots",                # Basic movement component
        "Rejuvenation Bead",    # Basic health regen component
        "Faerie Charm"          # Basic mana regen component
    ]
}

class ItemTestResult:
    def __init__(self):
        self.total_items = 0
        self.successful_scrapes = 0
        self.successful_type_classifications = 0
        self.section_extraction_stats = {}
        self.failed_items: List[Dict[str, Any]] = []
        self.error_summary: Dict[str, int] = {}
        self.type_classification_accuracy = {}
        self.start_time = time.time()
        
    def add_success(self, item: str, test_type: str, expected_type: str = None, actual_type: str = None):
        if test_type == "scrape":
            self.successful_scrapes += 1
        elif test_type == "type_classification":
            self.successful_type_classifications += 1
            
            # Track type classification accuracy
            if expected_type and actual_type:
                if expected_type not in self.type_classification_accuracy:
                    self.type_classification_accuracy[expected_type] = {'correct': 0, 'total': 0}
                self.type_classification_accuracy[expected_type]['total'] += 1
                if expected_type.lower() == actual_type.lower():
                    self.type_classification_accuracy[expected_type]['correct'] += 1
                    
    def add_section_success(self, section_name: str):
        if section_name not in self.section_extraction_stats:
            self.section_extraction_stats[section_name] = {'success': 0, 'total': 0}
        self.section_extraction_stats[section_name]['success'] += 1
        self.section_extraction_stats[section_name]['total'] += 1
    
    def add_section_failure(self, section_name: str):
        if section_name not in self.section_extraction_stats:
            self.section_extraction_stats[section_name] = {'success': 0, 'total': 0}
        self.section_extraction_stats[section_name]['total'] += 1
            
    def add_failure(self, item: str, test_type: str, error: str):
        self.failed_items.append({
            "item": item,
            "test_type": test_type,
            "error": str(error)
        })
        
        # Track error types
        error_type = type(error).__name__ if hasattr(error, '__class__') else "Unknown"
        self.error_summary[error_type] = self.error_summary.get(error_type, 0) + 1
        
    def print_summary(self):
        elapsed_time = time.time() - self.start_time
        
        print("\n" + "="*80)
        print("🔍 ITEM DATA SCRAPER TESTING SUMMARY")
        print("="*80)
        print(f"⏱️  Total Time: {elapsed_time:.2f} seconds")
        print(f"⚔️  Total Items Tested: {self.total_items}")
        print(f"✅ Successful Scrapes: {self.successful_scrapes}/{self.total_items} ({(self.successful_scrapes/self.total_items*100):.1f}%)")
        print(f"🏷️  Type Classification Success: {self.successful_type_classifications}/{self.total_items} ({(self.successful_type_classifications/self.total_items*100):.1f}%)")
        
        # Type classification accuracy by category
        if self.type_classification_accuracy:
            print(f"\n📊 Type Classification Accuracy by Category:")
            for item_type, stats in self.type_classification_accuracy.items():
                accuracy = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
                print(f"   {item_type.title()}: {stats['correct']}/{stats['total']} ({accuracy:.1f}%)")
        
        # Section extraction statistics
        if self.section_extraction_stats:
            print(f"\n📋 Section Extraction Statistics:")
            for section, stats in self.section_extraction_stats.items():
                success_rate = (stats['success'] / stats['total'] * 100) if stats['total'] > 0 else 0
                print(f"   {section}: {stats['success']}/{stats['total']} ({success_rate:.1f}%)")
        
        if self.failed_items:
            print(f"\n❌ Failed Tests: {len(self.failed_items)}")
            print("\n🔍 Error Summary:")
            for error_type, count in self.error_summary.items():
                print(f"   {error_type}: {count} occurrences")
                
            print("\n📝 Failed Items Details:")
            for failure in self.failed_items[:10]:  # Show first 10 failures
                print(f"   {failure['item']} ({failure['test_type']}): {failure['error'][:100]}...")
            
            if len(self.failed_items) > 10:
                print(f"   ... and {len(self.failed_items) - 10} more failures")
        
        print("\n" + "="*80)

async def test_item_data_scraping(scraper: ItemDataScraper, item: str, expected_type: str, result: ItemTestResult) -> Dict[str, Any]:
    """Test item data scraping functionality for a single item."""
    item_results = {
        "item": item,
        "expected_type": expected_type,
        "actual_type": None,
        "scrape_status": None,
        "sections_extracted": [],
        "errors": []
    }
    
    # Test 1: Full item data scraping
    try:
        item_data = await scraper.scrape_item_data(item)
        if item_data and item_data.get('item_name'):
            item_results["scrape_status"] = "SUCCESS"
            result.add_success(item, "scrape")
            
            # Extract type classification info
            actual_type = item_data.get('item_type', 'unknown')
            item_results["actual_type"] = actual_type
            
            # Test type classification accuracy
            if actual_type != 'unknown':
                result.add_success(item, "type_classification", expected_type, actual_type)
            
            # Track section extraction success
            sections_found = []
            if 'stats' in item_data:
                sections_found.append('stats')
                result.add_section_success('stats')
            else:
                result.add_section_failure('stats')
                
            if 'recipe' in item_data:
                sections_found.append('recipe')
                result.add_section_success('recipe')
            else:
                result.add_section_failure('recipe')
                
            if 'cost_analysis' in item_data:
                sections_found.append('cost_analysis')
                result.add_section_success('cost_analysis')
            else:
                result.add_section_failure('cost_analysis')
                
            if 'notes' in item_data:
                sections_found.append('notes')
                result.add_section_success('notes')
            else:
                result.add_section_failure('notes')
                
            if expected_type == 'completed':
                if 'map_differences' in item_data:
                    sections_found.append('map_differences')
                    result.add_section_success('map_differences')
                else:
                    result.add_section_failure('map_differences')
                    
                if 'similar_items' in item_data:
                    sections_found.append('similar_items')
                    result.add_section_success('similar_items')
                else:
                    result.add_section_failure('similar_items')
            else:
                # Basic/Epic items
                if 'builds_info' in item_data:
                    sections_found.append('builds_info')
                    result.add_section_success('builds_info')
                else:
                    result.add_section_failure('builds_info')
                    
                if 'old_icons' in item_data:
                    sections_found.append('old_icons')
                    result.add_section_success('old_icons')
                else:
                    result.add_section_failure('old_icons')
            
            item_results["sections_extracted"] = sections_found
        else:
            item_results["scrape_status"] = "FAILED - No data returned"
            result.add_failure(item, "scrape", "No data returned")
    except Exception as e:
        item_results["scrape_status"] = f"ERROR - {e}"
        item_results["errors"].append(f"Scraping: {e}")
        result.add_failure(item, "scrape", e)
    
    return item_results

async def test_all_item_types():
    """Test item data scraping for all item types."""
    print("🧪 Starting Comprehensive Item Data Scraper Testing")
    print("=" * 60)
    
    total_items = sum(len(items) for items in TEST_ITEMS.values())
    print(f"⚔️  Testing {total_items} items across 3 categories")
    print("🎯 Tests: Data Scraping, Type Classification, Section Extraction")
    print("⏱️  Estimated time: ~15-25 minutes")
    print("=" * 60)
    
    # Initialize scraper
    scraper = ItemDataScraper()
    result = ItemTestResult()
    result.total_items = total_items
    
    # Store detailed results
    detailed_results = []
    
    try:
        item_count = 0
        
        for category, items in TEST_ITEMS.items():
            print(f"\n🏷️  Testing {category.title()} Items ({len(items)} items)")
            print("-" * 40)
            
            for item in items:
                item_count += 1
                print(f"\n[{item_count:3d}/{total_items}] Testing {item}...")
                
                item_result = await test_item_data_scraping(scraper, item, category, result)
                detailed_results.append(item_result)
                
                # Print quick status
                status_icons = []
                if item_result["scrape_status"] == "SUCCESS":
                    status_icons.append("✅")
                if item_result["actual_type"] and item_result["actual_type"] != "unknown":
                    status_icons.append("🏷️")
                if item_result["sections_extracted"]:
                    status_icons.append(f"📋({len(item_result['sections_extracted'])})")
                if item_result["errors"]:
                    status_icons.append("❌")
                    
                print(f"              Status: {' '.join(status_icons) if status_icons else '❌'}")
                print(f"              Type: {item_result['actual_type'] or 'Unknown'}")
                print(f"              Sections: {', '.join(item_result['sections_extracted']) if item_result['sections_extracted'] else 'None'}")
                
                # Brief pause to avoid overwhelming the system
                if item_count % 5 == 0:
                    print(f"\n⏸️  Progress checkpoint: {item_count}/{total_items} completed")
                    await asyncio.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Testing interrupted by user")
        print(f"📊 Tested {item_count}/{total_items} items before interruption")
        
    finally:
        # Cleanup scraper resources
        if hasattr(scraper, 'close'):
            await scraper.close()
    
    # Print summary
    result.print_summary()
    
    # Save detailed results
    output_file = "item_scraper_test_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "summary": {
                "total_items": result.total_items,
                "successful_scrapes": result.successful_scrapes,
                "successful_type_classifications": result.successful_type_classifications,
                "section_extraction_stats": result.section_extraction_stats,
                "type_classification_accuracy": result.type_classification_accuracy,
                "total_failures": len(result.failed_items),
                "error_summary": result.error_summary,
                "test_duration": time.time() - result.start_time
            },
            "detailed_results": detailed_results,
            "failed_items": result.failed_items
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Detailed results saved to: {output_file}")
    print(f"📋 You can review individual item results and errors in the JSON file")

async def test_specific_sections():
    """Test specific section extraction functionality."""
    print("\n🔬 Testing Specific Section Extraction")
    print("=" * 50)
    
    scraper = ItemDataScraper()
    
    # Test specific sections on known items
    test_cases = [
        ("Echoes of Helia", ["stats", "recipe"]),
        ("Eclipse", ["cost_analysis", "notes"]),
        ("Kindlegem", ["builds_info"]), 
        ("Long Sword", ["similar_items"])
    ]
    
    try:
        for item, sections in test_cases:
            print(f"\n🎯 Testing {item} - Sections: {', '.join(sections)}")
            
            try:
                result = await scraper.scrape_item_data(item, sections=sections)
                if result:
                    found_sections = [s for s in sections if s in result]
                    print(f"   ✅ Found sections: {', '.join(found_sections)}")
                    print(f"   📊 Total data keys: {list(result.keys())}")
                else:
                    print("   ❌ No data returned")
            except Exception as e:
                print(f"   💥 Error: {e}")
    
    finally:
        if hasattr(scraper, 'close'):
            await scraper.close()

if __name__ == "__main__":
    print("🚀 Item Data Scraper Comprehensive Testing")
    print("=" * 50)
    print("This will test item data scraping functionality across all item types")
    print("Press Ctrl+C to interrupt testing at any time")
    print("=" * 50)
    
    try:
        # Run main tests
        asyncio.run(test_all_item_types())
        
        # Run specific section tests
        asyncio.run(test_specific_sections())
        
    except KeyboardInterrupt:
        print("\n👋 Testing stopped by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
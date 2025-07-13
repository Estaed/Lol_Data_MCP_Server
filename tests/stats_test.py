#!/usr/bin/env python3
"""
Comprehensive Stats Testing for All Champions
===========================================

This script tests the StatsService functionality across all League of Legends champions
to ensure robust implementation and identify any champions with special requirements.

Usage:
    python tests/stats_test.py

Features:
- Tests basic/default stats for all champions
- Tests level 6 specific stats for all champions
- Tests unit radius data extraction
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
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.stats_service import StatsService

# Complete list of League of Legends champions (as of 2024)
CHAMPIONS = [
    "Aatrox", "Ahri", "Akali", "Akshan", "Alistar", "Amumu", "Anivia", "Annie", "Aphelios", "Ashe",
    "Aurelion Sol", "Azir", "Bard", "Bel'Veth", "Blitzcrank", "Brand", "Braum", "Caitlyn", "Camille",
    "Cassiopeia", "Cho'Gath", "Corki", "Darius", "Diana", "Dr. Mundo", "Draven", "Ekko", "Elise",
    "Evelynn", "Ezreal", "Fiddlesticks", "Fiora", "Fizz", "Galio", "Gangplank", "Garen", "Gnar",
    "Gragas", "Graves", "Gwen", "Hecarim", "Heimerdinger", "Illaoi", "Irelia", "Ivern", "Janna",
    "Jarvan IV", "Jax", "Jayce", "Jhin", "Jinx", "Kai'Sa", "Kalista", "Karma", "Karthus", "Kassadin",
    "Katarina", "Kayle", "Kayn", "Kennen", "Kha'Zix", "Kindred", "Kled", "Kog'Maw", "LeBlanc",
    "Lee Sin", "Leona", "Lillia", "Lissandra", "Lucian", "Lulu", "Lux", "Malphite", "Malzahar",
    "Maokai", "Master Yi", "Miss Fortune", "Mordekaiser", "Morgana", "Nami", "Nasus", "Nautilus",
    "Neeko", "Nidalee", "Nilah", "Nocturne", "Nunu & Willump", "Olaf", "Orianna", "Ornn", "Pantheon",
    "Poppy", "Pyke", "Qiyana", "Quinn", "Rakan", "Rammus", "Rek'Sai", "Rell", "Renata Glasc",
    "Renekton", "Rengar", "Riven", "Rumble", "Ryze", "Samira", "Sejuani", "Senna", "Seraphine",
    "Sett", "Shaco", "Shen", "Shyvana", "Singed", "Sion", "Sivir", "Skarner", "Sona", "Soraka",
    "Swain", "Sylas", "Syndra", "Tahm Kench", "Taliyah", "Talon", "Taric", "Teemo", "Thresh",
    "Tristana", "Trundle", "Tryndamere", "Twisted Fate", "Twitch", "Udyr", "Urgot", "Varus",
    "Vayne", "Veigar", "Vel'Koz", "Vex", "Vi", "Viego", "Viktor", "Vladimir", "Volibear",
    "Warwick", "Wukong", "Xayah", "Xerath", "Xin Zhao", "Yasuo", "Yone", "Yorick", "Yuumi",
    "Zac", "Zed", "Zeri", "Ziggs", "Zilean", "Zoe", "Zyra"
]

class StatsTestResult:
    def __init__(self):
        self.total_champions = 0
        self.successful_basic_stats = 0
        self.successful_level6_stats = 0
        self.successful_unit_radius = 0
        self.failed_champions: List[Dict[str, Any]] = []
        self.error_summary: Dict[str, int] = {}
        self.start_time = time.time()
        
    def add_success(self, champion: str, test_type: str):
        if test_type == "basic_stats":
            self.successful_basic_stats += 1
        elif test_type == "level6_stats":
            self.successful_level6_stats += 1
        elif test_type == "unit_radius":
            self.successful_unit_radius += 1
            
    def add_failure(self, champion: str, test_type: str, error: str):
        self.failed_champions.append({
            "champion": champion,
            "test_type": test_type,
            "error": str(error)
        })
        
        # Track error types
        error_type = type(error).__name__ if hasattr(error, '__class__') else "Unknown"
        self.error_summary[error_type] = self.error_summary.get(error_type, 0) + 1
        
    def print_summary(self):
        elapsed_time = time.time() - self.start_time
        
        print("\n" + "="*80)
        print("📊 CHAMPION STATS TESTING SUMMARY")
        print("="*80)
        print(f"⏱️  Total Time: {elapsed_time:.2f} seconds")
        print(f"🎮 Total Champions Tested: {self.total_champions}")
        print(f"✅ Basic/Default Stats Success: {self.successful_basic_stats}/{self.total_champions} ({(self.successful_basic_stats/self.total_champions*100):.1f}%)")
        print(f"📈 Level 6 Stats Success: {self.successful_level6_stats}/{self.total_champions} ({(self.successful_level6_stats/self.total_champions*100):.1f}%)")
        print(f"📐 Unit Radius Success: {self.successful_unit_radius}/{self.total_champions} ({(self.successful_unit_radius/self.total_champions*100):.1f}%)")
        
        if self.failed_champions:
            print(f"\n❌ Failed Tests: {len(self.failed_champions)}")
            print("\n🔍 Error Summary:")
            for error_type, count in self.error_summary.items():
                print(f"   {error_type}: {count} occurrences")
                
            print("\n📝 Failed Champions Details:")
            for failure in self.failed_champions[:10]:  # Show first 10 failures
                print(f"   {failure['champion']} ({failure['test_type']}): {failure['error'][:100]}...")
            
            if len(self.failed_champions) > 10:
                print(f"   ... and {len(self.failed_champions) - 10} more failures")
        
        print("\n" + "="*80)

async def test_champion_stats(service: StatsService, champion: str, result: StatsTestResult) -> Dict[str, Any]:
    """Test basic and level 6 stat functionality for a single champion."""
    champion_results = {
        "champion": champion,
        "basic_stats": None,
        "level_6_stats": None,
        "unit_radius": False,
        "errors": []
    }
    
    # Test 1: Basic/Default Stats (no level specified - gives level 1-18 range default)
    try:
        basic_stats = await service.get_champion_stats(champion)
        if basic_stats and basic_stats.get('stats'):
            champion_results["basic_stats"] = "SUCCESS"
            result.add_success(champion, "basic_stats")
            
            # Check for unit radius data in basic stats
            stats_data = basic_stats.get('stats', {})
            if any(key.endswith('_radius') for key in stats_data.keys()):
                champion_results["unit_radius"] = True
                result.add_success(champion, "unit_radius")
        else:
            champion_results["basic_stats"] = "FAILED - No stats returned"
            result.add_failure(champion, "basic_stats", "No stats returned")
    except Exception as e:
        champion_results["basic_stats"] = f"ERROR - {e}"
        champion_results["errors"].append(f"Basic stats: {e}")
        result.add_failure(champion, "basic_stats", e)
    
    # Test 2: Level 6 Stats
    try:
        level_6_stats = await service.get_champion_stats(champion, level=6)
        if level_6_stats and level_6_stats.get('stats'):
            champion_results["level_6_stats"] = "SUCCESS"
            result.add_success(champion, "level6_stats")
        else:
            champion_results["level_6_stats"] = "FAILED - No level 6 stats returned"
            result.add_failure(champion, "level6_stats", "No level 6 stats returned")
    except Exception as e:
        champion_results["level_6_stats"] = f"ERROR - {e}"
        champion_results["errors"].append(f"Level 6 stats: {e}")
        result.add_failure(champion, "level6_stats", e)
    
    return champion_results

async def test_all_champion_stats():
    """Test stats functionality for all champions."""
    print("🧪 Starting Comprehensive Champion Stats Testing")
    print("=" * 60)
    print(f"📋 Testing {len(CHAMPIONS)} champions")
    print("🎯 Tests: Basic/Default Stats, Level 6 Stats, Unit Radius")
    print("⏱️  Estimated time: ~20-30 minutes")
    print("=" * 60)
    
    # Initialize service
    service = StatsService()
    result = StatsTestResult()
    result.total_champions = len(CHAMPIONS)
    
    # Store detailed results
    detailed_results = []
    
    try:
        for i, champion in enumerate(CHAMPIONS, 1):
            print(f"\n[{i:3d}/{len(CHAMPIONS)}] Testing {champion}...")
            
            champion_result = await test_champion_stats(service, champion, result)
            detailed_results.append(champion_result)
            
            # Print quick status
            status_icons = []
            if champion_result["basic_stats"] == "SUCCESS":
                status_icons.append("📊")
            if champion_result["level_6_stats"] == "SUCCESS":
                status_icons.append("📈")
            if champion_result["unit_radius"]:
                status_icons.append("📐")
            if champion_result["errors"]:
                status_icons.append("❌")
                
            print(f"              Status: {' '.join(status_icons) if status_icons else '❌'}")
            
            # Brief pause to avoid overwhelming the system
            if i % 10 == 0:
                print(f"\n⏸️  Progress checkpoint: {i}/{len(CHAMPIONS)} completed")
                await asyncio.sleep(2)
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Testing interrupted by user")
        print(f"📊 Tested {i}/{len(CHAMPIONS)} champions before interruption")
        
    finally:
        # Cleanup service resources
        if hasattr(service, 'cleanup'):
            await service.cleanup()
    
    # Print summary
    result.print_summary()
    
    # Save detailed results
    output_file = "stats_test_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "summary": {
                "total_champions": result.total_champions,
                "successful_basic_stats": result.successful_basic_stats,
                "successful_level6_stats": result.successful_level6_stats,
                "successful_unit_radius": result.successful_unit_radius,
                "total_failures": len(result.failed_champions),
                "error_summary": result.error_summary,
                "test_duration": time.time() - result.start_time
            },
            "detailed_results": detailed_results,
            "failed_champions": result.failed_champions
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Detailed results saved to: {output_file}")
    print(f"📋 You can review individual champion results and errors in the JSON file")

if __name__ == "__main__":
    print("🚀 Champion Stats Comprehensive Testing")
    print("=" * 50)
    print("This will test stats functionality for all LoL champions")
    print("Press Ctrl+C to interrupt testing at any time")
    print("=" * 50)
    
    try:
        asyncio.run(test_all_champion_stats())
    except KeyboardInterrupt:
        print("\n👋 Testing stopped by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc() 
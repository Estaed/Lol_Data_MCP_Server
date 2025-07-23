#!/usr/bin/env python3
"""
Comprehensive Abilities Testing for All Champions
===============================================

This script tests the AbilitiesService functionality across all League of Legends champions
to ensure robust implementation and identify any champions with special requirements.

Usage:
    python tests/abilities_test.py

Features:
- Tests all abilities (Passive, Q, W, E, R) for all champions
- Tests enhanced details (targeting input, damage classification, counters)
- Handles dual-form champions (Nidalee, Jayce, etc.)
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
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.champions.abilities_service import AbilitiesService

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

# Known dual-form champions that require special handling
DUAL_FORM_CHAMPIONS = [
    "Nidalee", "Jayce", "Elise", "Gnar", "Shyvana", "Udyr", "Kayn"
]

class AbilitiesTestResult:
    def __init__(self):
        self.total_champions = 0
        self.successful_all_abilities = 0
        self.successful_individual_abilities = 0
        self.successful_enhanced_details = 0
        self.dual_form_detected = 0
        self.failed_champions: List[Dict[str, Any]] = []
        self.error_summary: Dict[str, int] = {}
        self.start_time = time.time()
        
    def add_success(self, champion: str, test_type: str):
        if test_type == "all_abilities":
            self.successful_all_abilities += 1
        elif test_type == "individual_abilities":
            self.successful_individual_abilities += 1
        elif test_type == "enhanced_details":
            self.successful_enhanced_details += 1
        elif test_type == "dual_form":
            self.dual_form_detected += 1
            
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
        print("🎮 CHAMPION ABILITIES TESTING SUMMARY")
        print("="*80)
        print(f"⏱️  Total Time: {elapsed_time:.2f} seconds")
        print(f"🎮 Total Champions Tested: {self.total_champions}")
        print(f"✅ All Abilities Success: {self.successful_all_abilities}/{self.total_champions} ({(self.successful_all_abilities/self.total_champions*100):.1f}%)")
        print(f"🎯 Individual Abilities Success: {self.successful_individual_abilities}/{self.total_champions} ({(self.successful_individual_abilities/self.total_champions*100):.1f}%)")
        print(f"🔍 Enhanced Details Success: {self.successful_enhanced_details}/{self.total_champions} ({(self.successful_enhanced_details/self.total_champions*100):.1f}%)")
        print(f"🔄 Dual-Form Detected: {self.dual_form_detected} champions")
        
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

async def test_champion_abilities(service: AbilitiesService, champion: str, result: AbilitiesTestResult) -> Dict[str, Any]:
    """Test all ability functionality for a single champion."""
    champion_results = {
        "champion": champion,
        "all_abilities": None,
        "passive_details": None,
        "q_details": None,
        "w_details": None,
        "e_details": None,
        "r_details": None,
        "dual_form": False,
        "enhanced_details_count": 0,
        "errors": []
    }
    
    # Test 1: Get All Abilities
    try:
        all_abilities = await service.get_champion_abilities(champion)
        if all_abilities and all_abilities.get('abilities'):
            abilities_data = all_abilities.get('abilities', {})
            ability_count = len(abilities_data)
            
            champion_results["all_abilities"] = f"SUCCESS - {ability_count} abilities"
            result.add_success(champion, "all_abilities")
            
            # Check if it's a dual-form champion
            if any(form_word in str(abilities_data).lower() for form_word in ['form', 'stance', 'mode']):
                champion_results["dual_form"] = True
                result.add_success(champion, "dual_form")
            
            # Count abilities for verification
            expected_abilities = ['passive', 'q', 'w', 'e', 'r']
            found_abilities = [slot for slot in expected_abilities if slot in abilities_data]
            if len(found_abilities) >= 4:  # At least 4 abilities (some champions might have different structures)
                result.add_success(champion, "individual_abilities")
                champion_results["individual_abilities"] = f"SUCCESS - Found {len(found_abilities)} abilities"
        else:
            champion_results["all_abilities"] = "FAILED - No abilities returned"
            result.add_failure(champion, "all_abilities", "No abilities returned")
    except Exception as e:
        champion_results["all_abilities"] = f"ERROR - {e}"
        champion_results["errors"].append(f"All abilities: {e}")
        result.add_failure(champion, "all_abilities", e)
    
    # Test 2: Enhanced Details for Each Ability (Task 2.1.11)
    ability_slots = ['Passive', 'Q', 'W', 'E', 'R']
    
    for slot in ability_slots:
        slot_key = slot.lower() + "_details"
        try:
            enhanced_ability = await service.get_ability_details(champion, slot)
            if enhanced_ability and enhanced_ability.get('ability'):
                ability_data = enhanced_ability.get('ability', {})
                
                # Check for enhanced details
                enhanced_details = ability_data.get('enhanced_details', {})
                if enhanced_details:
                    champion_results["enhanced_details_count"] += 1
                    champion_results[slot_key] = f"SUCCESS - Enhanced details: {list(enhanced_details.keys())}"
                else:
                    champion_results[slot_key] = "SUCCESS - Basic details only"
                    
            else:
                champion_results[slot_key] = "FAILED - No ability data"
                
        except Exception as e:
            champion_results[slot_key] = f"ERROR - {e}"
            champion_results["errors"].append(f"{slot} details: {e}")
    
    # Overall enhanced details success
    if champion_results["enhanced_details_count"] > 0:
        result.add_success(champion, "enhanced_details")
    
    return champion_results

async def test_all_champion_abilities():
    """Test abilities functionality for all champions."""
    print("🧪 Starting Comprehensive Champion Abilities Testing")
    print("=" * 60)
    print(f"📋 Testing {len(CHAMPIONS)} champions")
    print("🎯 Tests: All Abilities, Individual Abilities (P/Q/W/E/R), Enhanced Details")
    print("🔄 Special handling for dual-form champions")
    print("⏱️  Estimated time: ~45-60 minutes")
    print("=" * 60)
    
    # Initialize service
    service = AbilitiesService(enable_wiki=True, use_cache=True)
    result = AbilitiesTestResult()
    result.total_champions = len(CHAMPIONS)
    
    # Store detailed results
    detailed_results = []
    
    try:
        for i, champion in enumerate(CHAMPIONS, 1):
            print(f"\n[{i:3d}/{len(CHAMPIONS)}] Testing {champion}...")
            
            # Add indicator for known dual-form champions
            dual_form_indicator = " 🔄" if champion in DUAL_FORM_CHAMPIONS else ""
            print(f"              Champion: {champion}{dual_form_indicator}")
            
            champion_result = await test_champion_abilities(service, champion, result)
            detailed_results.append(champion_result)
            
            # Print quick status
            status_icons = []
            if champion_result["all_abilities"] and "SUCCESS" in champion_result["all_abilities"]:
                status_icons.append("🎮")
            if champion_result["enhanced_details_count"] > 0:
                status_icons.append(f"🔍{champion_result['enhanced_details_count']}")
            if champion_result["dual_form"]:
                status_icons.append("🔄")
            if champion_result["errors"]:
                status_icons.append("❌")
                
            print(f"              Status: {' '.join(status_icons) if status_icons else '❌'}")
            
            # Brief pause to avoid overwhelming the system
            if i % 5 == 0:  # More frequent pauses for abilities testing (uses Selenium)
                print(f"\n⏸️  Progress checkpoint: {i}/{len(CHAMPIONS)} completed")
                print(f"   Enhanced details working for {result.successful_enhanced_details} champions so far")
                await asyncio.sleep(3)
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Testing interrupted by user")
        print(f"📊 Tested {i}/{len(CHAMPIONS)} champions before interruption")
        
    finally:
        # Cleanup service resources
        if hasattr(service, 'cleanup'):
            await service.cleanup()
    
    # Print summary
    result.print_summary()
    
    # Additional analysis
    print("\n🔍 ADDITIONAL ANALYSIS")
    print("=" * 40)
    
    # Enhanced details analysis
    enhanced_details_champions = [r for r in detailed_results if r["enhanced_details_count"] > 0]
    if enhanced_details_champions:
        print(f"🎯 Champions with Enhanced Details: {len(enhanced_details_champions)}")
        top_enhanced = sorted(enhanced_details_champions, key=lambda x: x["enhanced_details_count"], reverse=True)[:5]
        for champ in top_enhanced:
            print(f"   {champ['champion']}: {champ['enhanced_details_count']} abilities with enhanced details")
    
    # Dual-form champions analysis
    dual_form_champions = [r for r in detailed_results if r["dual_form"]]
    if dual_form_champions:
        print(f"\n🔄 Detected Dual-Form Champions: {len(dual_form_champions)}")
        for champ in dual_form_champions:
            print(f"   {champ['champion']}")
    
    # Save detailed results
    output_file = "abilities_test_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "summary": {
                "total_champions": result.total_champions,
                "successful_all_abilities": result.successful_all_abilities,
                "successful_individual_abilities": result.successful_individual_abilities,
                "successful_enhanced_details": result.successful_enhanced_details,
                "dual_form_detected": result.dual_form_detected,
                "total_failures": len(result.failed_champions),
                "error_summary": result.error_summary,
                "test_duration": time.time() - result.start_time
            },
            "detailed_results": detailed_results,
            "failed_champions": result.failed_champions,
            "enhanced_details_champions": [r["champion"] for r in enhanced_details_champions],
            "dual_form_champions": [r["champion"] for r in dual_form_champions]
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Detailed results saved to: {output_file}")
    print(f"📋 You can review individual champion results and errors in the JSON file")

if __name__ == "__main__":
    print("🚀 Champion Abilities Comprehensive Testing")
    print("=" * 50)
    print("This will test abilities functionality for all LoL champions")
    print("Including enhanced details from Task 2.1.11 implementation")
    print("Press Ctrl+C to interrupt testing at any time")
    print("=" * 50)
    
    try:
        asyncio.run(test_all_champion_abilities())
    except KeyboardInterrupt:
        print("\n👋 Testing stopped by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc() 
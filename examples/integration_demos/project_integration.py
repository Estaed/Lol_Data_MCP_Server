"""
Project Integration Demo

This example demonstrates how to integrate the LoL Data MCP Server
into larger projects and applications, showing practical use cases
for AI training, data analysis, and game development.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

try:
    from services.champion_service import ChampionService
except ImportError:
    # Fallback for when service is not available
    print("Note: ChampionService not available - using mock implementation")
    
    class ChampionService:
        """Mock ChampionService for demonstration purposes."""
        
        async def get_champion_data(self, champion_name: str):
            """Mock method returning sample data structure."""
            from types import SimpleNamespace
            
            # Return mock data structure similar to real service
            return SimpleNamespace(
                name=champion_name,
                role="Support" if champion_name == "Taric" else "ADC",
                stats=SimpleNamespace(
                    health=575,
                    health_per_level=85,
                    mana=300,
                    mana_per_level=60,
                    attack_damage=55,
                    attack_damage_per_level=3.5,
                    armor=40,
                    armor_per_level=3.5,
                    magic_resist=32,
                    magic_resist_per_level=1.25,
                    movement_speed=340,
                    attack_range=150,
                ),
                abilities=SimpleNamespace(
                    passive=SimpleNamespace(
                        name="Bravado",
                        description="Mock passive ability"
                    ),
                    q=SimpleNamespace(
                        name="Starlight's Touch",
                        description="Mock Q ability",
                        cooldown=14,
                        cost=60
                    ),
                    w=SimpleNamespace(
                        name="Bastion", 
                        description="Mock W ability",
                        cooldown=18,
                        cost=50
                    ),
                    e=SimpleNamespace(
                        name="Dazzle",
                        description="Mock E ability",
                        cooldown=13,
                        cost=70
                    ),
                    r=SimpleNamespace(
                        name="Cosmic Radiance",
                        description="Mock R ability",
                        cooldown=160,
                        cost=100
                    ),
                )
            )


class LoLDataIntegrator:
    """
    Integration wrapper for LoL Data MCP Server functionality.
    
    This class provides a Python API for integrating LoL data
    into training pipelines, analysis tools, and game simulations.
    """
    
    def __init__(self):
        self.champion_service = ChampionService()
    
    async def get_training_data(self, champion_name: str) -> Dict[str, Any]:
        """
        Get structured training data for a champion.
        
        Args:
            champion_name: Name of the champion
            
        Returns:
            Structured data suitable for ML training
        """
        try:
            champion_data = await self.champion_service.get_champion_data(champion_name)
            
            # Convert to training-friendly format
            training_data = {
                "champion_id": champion_data.name,
                "role": champion_data.role,
                "stats": {
                    "health": champion_data.stats.health,
                    "health_per_level": champion_data.stats.health_per_level,
                    "mana": champion_data.stats.mana,
                    "mana_per_level": champion_data.stats.mana_per_level,
                    "attack_damage": champion_data.stats.attack_damage,
                    "attack_damage_per_level": champion_data.stats.attack_damage_per_level,
                    "armor": champion_data.stats.armor,
                    "armor_per_level": champion_data.stats.armor_per_level,
                    "magic_resist": champion_data.stats.magic_resist,
                    "magic_resist_per_level": champion_data.stats.magic_resist_per_level,
                    "movement_speed": champion_data.stats.movement_speed,
                    "attack_range": champion_data.stats.attack_range,
                },
                "abilities": [
                    {
                        "slot": "passive",
                        "name": champion_data.abilities.passive.name,
                        "description": champion_data.abilities.passive.description,
                    },
                    {
                        "slot": "Q",
                        "name": champion_data.abilities.q.name,
                        "description": champion_data.abilities.q.description,
                        "cooldown": champion_data.abilities.q.cooldown,
                        "cost": champion_data.abilities.q.cost,
                    },
                    {
                        "slot": "W", 
                        "name": champion_data.abilities.w.name,
                        "description": champion_data.abilities.w.description,
                        "cooldown": champion_data.abilities.w.cooldown,
                        "cost": champion_data.abilities.w.cost,
                    },
                    {
                        "slot": "E",
                        "name": champion_data.abilities.e.name, 
                        "description": champion_data.abilities.e.description,
                        "cooldown": champion_data.abilities.e.cooldown,
                        "cost": champion_data.abilities.e.cost,
                    },
                    {
                        "slot": "R",
                        "name": champion_data.abilities.r.name,
                        "description": champion_data.abilities.r.description,
                        "cooldown": champion_data.abilities.r.cooldown,
                        "cost": champion_data.abilities.r.cost,
                    },
                ],
            }
            
            return training_data
            
        except Exception as e:
            print(f"Error getting training data for {champion_name}: {e}")
            return {}
    
    async def get_champion_comparison_data(self, champion_names: List[str]) -> Dict[str, Any]:
        """
        Get comparative data for multiple champions.
        
        Args:
            champion_names: List of champion names to compare
            
        Returns:
            Comparison data structure
        """
        comparison_data = {
            "champions": [],
            "stats_comparison": {},
            "abilities_summary": {}
        }
        
        for champion_name in champion_names:
            champion_data = await self.get_training_data(champion_name)
            if champion_data:
                comparison_data["champions"].append(champion_data)
        
        # Generate comparison metrics
        if comparison_data["champions"]:
            stats_keys = comparison_data["champions"][0]["stats"].keys()
            for stat in stats_keys:
                comparison_data["stats_comparison"][stat] = {
                    champion["champion_id"]: champion["stats"][stat]
                    for champion in comparison_data["champions"]
                }
        
        return comparison_data


async def demo_training_integration():
    """Demonstrate integration for ML training pipelines."""
    print("\n🤖 TRAINING INTEGRATION DEMO")
    print("=" * 50)
    
    integrator = LoLDataIntegrator()
    
    # Get training data for Taric
    print("📊 Getting training data for Taric...")
    taric_training_data = await integrator.get_training_data("Taric")
    
    if taric_training_data:
        print("✅ Training data structure:")
        print(f"  - Champion: {taric_training_data['champion_id']}")
        print(f"  - Role: {taric_training_data['role']}")
        print(f"  - Health at level 1: {taric_training_data['stats']['health']}")
        print(f"  - Number of abilities: {len(taric_training_data['abilities'])}")
        
        # Example: Save training data to file
        output_file = Path(__file__).parent / "taric_training_data.json"
        with open(output_file, 'w') as f:
            json.dump(taric_training_data, f, indent=2)
        print(f"💾 Training data saved to: {output_file}")


async def demo_comparison_analysis():
    """Demonstrate champion comparison analysis."""
    print("\n📈 COMPARISON ANALYSIS DEMO")
    print("=" * 50)
    
    integrator = LoLDataIntegrator()
    
    # Compare support champions
    support_champions = ["Taric", "Ezreal"]  # Using available mock data
    print(f"⚔️ Comparing champions: {', '.join(support_champions)}")
    
    comparison_data = await integrator.get_champion_comparison_data(support_champions)
    
    if comparison_data["champions"]:
        print("✅ Comparison results:")
        
        # Health comparison
        health_stats = comparison_data["stats_comparison"].get("health", {})
        print("\n💚 Health comparison:")
        for champion, health in health_stats.items():
            print(f"  - {champion}: {health} HP")
        
        # Attack damage comparison
        ad_stats = comparison_data["stats_comparison"].get("attack_damage", {})
        print("\n⚔️ Attack damage comparison:")
        for champion, ad in ad_stats.items():
            print(f"  - {champion}: {ad} AD")


async def demo_simulation_integration():
    """Demonstrate integration with game simulation systems."""
    print("\n🎮 SIMULATION INTEGRATION DEMO")
    print("=" * 50)
    
    integrator = LoLDataIntegrator()
    
    # Get data for simulation
    print("🔧 Preparing simulation data...")
    taric_data = await integrator.get_training_data("Taric")
    
    if taric_data:
        # Example simulation configuration
        simulation_config = {
            "champion": {
                "name": taric_data["champion_id"],
                "role": taric_data["role"],
                "base_stats": taric_data["stats"],
            },
            "abilities": {
                ability["slot"]: {
                    "name": ability["name"],
                    "cooldown": ability.get("cooldown", 0),
                    "cost": ability.get("cost", 0),
                }
                for ability in taric_data["abilities"]
            },
        }
        
        print("✅ Simulation configuration generated:")
        print(f"  - Champion: {simulation_config['champion']['name']}")
        print(f"  - Role: {simulation_config['champion']['role']}")
        print(f"  - Abilities configured: {len(simulation_config['abilities'])}")
        
        # Save simulation config
        config_file = Path(__file__).parent / "simulation_config.json"
        with open(config_file, 'w') as f:
            json.dump(simulation_config, f, indent=2)
        print(f"💾 Simulation config saved to: {config_file}")


async def main():
    """Main demonstration function."""
    print("🎯 LoL Data MCP Server - Project Integration Demos")
    print("=" * 60)
    
    try:
        # Run all demos
        await demo_training_integration()
        await demo_comparison_analysis()
        await demo_simulation_integration()
        
        print("\n🎉 All integration demos completed successfully!")
        print("\nThese examples show how to:")
        print("  ✅ Extract training data for ML pipelines")
        print("  ✅ Compare champions for analysis")
        print("  ✅ Generate simulation configurations")
        print("  ✅ Integrate with larger game development projects")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 
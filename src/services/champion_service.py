"""
Champion Service for League of Legends MCP Server

This module provides service layer functionality for retrieving and processing
champion data. It handles data validation, error handling, and logging for
champion-related operations.
"""

import logging
from typing import Dict, Any, Optional
import structlog

from pydantic import BaseModel, Field, ValidationError
from ..tools import GetChampionDataInput


# Response Models
class ChampionStats(BaseModel):
    """Champion base statistics model"""
    
    health: float = Field(..., description="Base health points")
    health_per_level: float = Field(..., description="Health gained per level")
    mana: float = Field(..., description="Base mana points")
    mana_per_level: float = Field(..., description="Mana gained per level")
    attack_damage: float = Field(..., description="Base attack damage")
    attack_damage_per_level: float = Field(..., description="AD gained per level")
    armor: float = Field(..., description="Base armor")
    armor_per_level: float = Field(..., description="Armor gained per level")
    magic_resist: float = Field(..., description="Base magic resistance")
    magic_resist_per_level: float = Field(..., description="MR gained per level")
    movement_speed: float = Field(..., description="Base movement speed")
    attack_range: float = Field(..., description="Attack range")
    attack_speed: float = Field(..., description="Base attack speed (attacks per second)")
    attack_speed_per_level: float = Field(..., description="Attack speed gained per level")


class AbilityInfo(BaseModel):
    """Champion ability information model"""
    
    name: str = Field(..., description="Ability name")
    description: str = Field(..., description="Ability description")
    cooldown: str = Field(..., description="Cooldown information")
    cost: str = Field(..., description="Ability cost (mana/energy)")
    range: str = Field(..., description="Ability range")
    effect: str = Field(..., description="Ability effect details")


class ChampionAbilities(BaseModel):
    """Champion abilities model"""
    
    passive: AbilityInfo = Field(..., description="Passive ability")
    q: AbilityInfo = Field(..., description="Q ability")
    w: AbilityInfo = Field(..., description="W ability")
    e: AbilityInfo = Field(..., description="E ability")
    r: AbilityInfo = Field(..., description="R (Ultimate) ability")


class ChampionData(BaseModel):
    """Complete champion data model"""
    
    name: str = Field(..., description="Champion name")
    title: str = Field(..., description="Champion title")
    roles: list[str] = Field(..., description="Primary roles")
    difficulty: int = Field(..., ge=1, le=10, description="Difficulty rating 1-10")
    stats: Optional[ChampionStats] = Field(None, description="Champion statistics")
    abilities: Optional[ChampionAbilities] = Field(None, description="Champion abilities")
    tags: list[str] = Field(default_factory=list, description="Champion tags")
    patch: str = Field(..., description="Current patch version")


class ChampionNotFoundError(Exception):
    """Exception raised when a champion is not found"""
    
    def __init__(self, champion_name: str):
        self.champion_name = champion_name
        super().__init__(f"Champion '{champion_name}' not found")


class ChampionService:
    """Service class for champion data operations"""
    
    def __init__(self):
        """Initialize the champion service with logging"""
        self.logger = structlog.get_logger(__name__)
        self._mock_data = self._initialize_mock_data()
    
    def _initialize_mock_data(self) -> Dict[str, ChampionData]:
        """Initialize mock champion data for development"""
        
        # Mock data for Taric (as specified in task requirements)
        taric_data = ChampionData(
            name="Taric",
            title="The Shield of Valoran",
            roles=["Support", "Top"],
            difficulty=5,
            stats=ChampionStats(
                health=575.0,
                health_per_level=90.0,
                mana=300.0,
                mana_per_level=60.0,
                attack_damage=55.0,
                attack_damage_per_level=3.5,
                armor=40.0,
                armor_per_level=4.0,
                magic_resist=32.0,
                magic_resist_per_level=1.25,
                movement_speed=340.0,
                attack_range=150.0,
                attack_speed=0.625,
                attack_speed_per_level=2.0
            ),
            abilities=ChampionAbilities(
                passive=AbilityInfo(
                    name="Bravado",
                    description="Taric's spells grant him and his Bastion charges that enhance his next two basic attacks to deal bonus magic damage, reduce his basic ability cooldowns, and grant him and his Bastion charges of Bravado.",
                    cooldown="N/A",
                    cost="N/A",
                    range="N/A",
                    effect="Enhanced basic attacks reduce cooldowns and grant charges"
                ),
                q=AbilityInfo(
                    name="Starlight's Touch",
                    description="Taric heals himself and his Bastion. Healing is increased based on charges of Bravado consumed.",
                    cooldown="14/13/12/11/10 seconds",
                    cost="60/65/70/75/80 mana + 3 charges",
                    range="Self/Bastion",
                    effect="Heals self and Bastion, enhanced by Bravado charges"
                ),
                w=AbilityInfo(
                    name="Bastion",
                    description="Taric shields himself and links to an ally champion. Linked allies gain Bastion passive and are healed by Taric's abilities.",
                    cooldown="20/18/16/14/12 seconds",
                    cost="60 mana",
                    range="800",
                    effect="Links to ally, shares abilities and provides passive benefits"
                ),
                e=AbilityInfo(
                    name="Dazzle",
                    description="Taric shoots out a beam of starlight that damages and stuns enemies. The stun duration increases with range.",
                    cooldown="13/12/11/10/9 seconds",
                    cost="60 mana",
                    range="575",
                    effect="Stuns enemies, duration increases with distance"
                ),
                r=AbilityInfo(
                    name="Cosmic Radiance",
                    description="After a delay, Taric and his Bastion become invulnerable for a short duration.",
                    cooldown="160/120/80 seconds",
                    cost="100 mana",
                    range="Self/Bastion",
                    effect="Grants invulnerability after delay to self and Bastion"
                )
            ),
            tags=["Support", "Fighter", "Tank"],
            patch="14.1"
        )
        
        # Add more mock champions for testing
        ezreal_data = ChampionData(
            name="Ezreal",
            title="The Prodigal Explorer",
            roles=["ADC", "Mid"],
            difficulty=7,
            stats=ChampionStats(
                health=530.0,
                health_per_level=88.0,
                mana=375.0,
                mana_per_level=70.0,
                attack_damage=62.0,
                attack_damage_per_level=4.0,
                armor=24.0,
                armor_per_level=4.2,
                magic_resist=30.0,
                magic_resist_per_level=1.3,
                movement_speed=325.0,
                attack_range=550.0,
                attack_speed=0.625,
                attack_speed_per_level=2.8
            ),
            abilities=ChampionAbilities(
                passive=AbilityInfo(
                    name="Rising Spell Force",
                    description="Hitting enemies with abilities grants attack speed.",
                    cooldown="N/A",
                    cost="N/A", 
                    range="N/A",
                    effect="Attack speed buff when hitting abilities"
                ),
                q=AbilityInfo(
                    name="Mystic Shot",
                    description="Fires a projectile that deals damage and reduces cooldowns on hit.",
                    cooldown="6.5/6/5.5/5/4.5 seconds",
                    cost="28/31/34/37/40 mana",
                    range="1150",
                    effect="Skillshot that reduces cooldowns on hit"
                ),
                w=AbilityInfo(
                    name="Essence Flux",
                    description="Fires an orb that damages enemies and marks them.",
                    cooldown="12/11/10/9/8 seconds",
                    cost="50/60/70/80/90 mana",
                    range="1000",
                    effect="Marks enemies for additional damage"
                ),
                e=AbilityInfo(
                    name="Arcane Shift",
                    description="Teleports to target location and fires a homing bolt.",
                    cooldown="25/22/19/16/13 seconds",
                    cost="90 mana",
                    range="475",
                    effect="Blink ability with damage component"
                ),
                r=AbilityInfo(
                    name="Trueshot Barrage",
                    description="Fires a global skillshot that damages all enemies hit.",
                    cooldown="120/105/90 seconds",
                    cost="100 mana",
                    range="Global",
                    effect="Global skillshot with decreasing damage"
                )
            ),
            tags=["Marksman", "Mage"],
            patch="14.1"
        )
        
        return {
            "taric": taric_data,
            "ezreal": ezreal_data
        }
    
    async def get_champion_data(
        self, 
        champion: str, 
        patch: str = "current", 
        include: list[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieve comprehensive champion data
        
        Args:
            champion: Champion name to retrieve data for
            patch: Game patch version (default: "current")
            include: List of data sections to include (stats, abilities, builds, history)
            
        Returns:
            Dictionary containing champion data based on include parameters
            
        Raises:
            ChampionNotFoundError: If champion is not found
            ValidationError: If input parameters are invalid
        """
        if include is None:
            include = ["stats", "abilities"]
        
        # Log the request
        self.logger.info(
            "Champion data request",
            champion=champion,
            patch=patch,
            include=include
        )
        
        try:
            # Validate input using Pydantic model
            validated_input = GetChampionDataInput(
                champion=champion,
                patch=patch,
                include=include
            )
            
            # Normalize champion name for lookup
            champion_key = champion.lower().strip()
            
            # Check if champion exists in mock data
            if champion_key not in self._mock_data:
                self.logger.warning(
                    "Champion not found", 
                    champion=champion,
                    available_champions=list(self._mock_data.keys())
                )
                raise ChampionNotFoundError(champion)
            
            # Get champion data
            champion_data = self._mock_data[champion_key]
            
            # Build response based on include parameters
            response = {
                "name": champion_data.name,
                "title": champion_data.title,
                "roles": champion_data.roles,
                "difficulty": champion_data.difficulty,
                "tags": champion_data.tags,
                "patch": champion_data.patch,
                "data_included": validated_input.include
            }
            
            # Add requested data sections
            if "stats" in validated_input.include and champion_data.stats:
                response["stats"] = champion_data.stats.model_dump()
            
            if "abilities" in validated_input.include and champion_data.abilities:
                response["abilities"] = champion_data.abilities.model_dump()
            
            if "builds" in validated_input.include:
                # Mock builds data for future implementation
                response["builds"] = {
                    "core_items": ["Mock Item 1", "Mock Item 2"],
                    "situational_items": ["Mock Item 3", "Mock Item 4"],
                    "note": "Builds data not yet implemented - mock data provided"
                }
            
            if "history" in validated_input.include:
                # Mock history data for future implementation
                response["history"] = {
                    "recent_changes": ["Mock change 1", "Mock change 2"],
                    "patch_notes": ["14.1: Updated stats"],
                    "note": "History data not yet implemented - mock data provided"
                }
            
            # Log successful response
            self.logger.info(
                "Champion data retrieved successfully",
                champion=champion,
                sections_included=len([k for k in response.keys() if k in validated_input.include])
            )
            
            return response
            
        except ValidationError as e:
            self.logger.error(
                "Input validation failed",
                champion=champion,
                errors=str(e)
            )
            raise
        
        except ChampionNotFoundError:
            # Re-raise the custom exception
            raise
        
        except Exception as e:
            self.logger.error(
                "Unexpected error retrieving champion data",
                champion=champion,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    def get_available_champions(self) -> list[str]:
        """
        Get list of available champions in the service
        
        Returns:
            List of champion names
        """
        return [champion_data.name for champion_data in self._mock_data.values()]
    
    async def validate_champion_exists(self, champion: str) -> bool:
        """
        Check if a champion exists in the service
        
        Args:
            champion: Champion name to check
            
        Returns:
            True if champion exists, False otherwise
        """
        champion_key = champion.lower().strip()
        return champion_key in self._mock_data
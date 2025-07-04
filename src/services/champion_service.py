"""
Champion Service for League of Legends MCP Server (Updated with WikiScraper Integration)

This module provides service layer functionality for retrieving and processing
champion data. It handles data validation, error handling, and logging for
champion-related operations with real wiki data and mock fallback.
"""

import logging
import re
import httpx
from typing import Dict, Any, Optional, List
import structlog

from pydantic import BaseModel, Field, ValidationError, field_validator
from src.data_sources.scrapers.wiki_scraper import WikiScraper, WikiScraperError, ChampionNotFoundError as WikiChampionNotFoundError


# Input Models (moved from tools.py to break circular import)
class GetChampionDataInput(BaseModel):
    """Input schema for get_champion_data tool"""

    champion: str = Field(..., description="Champion name")
    patch: str = Field("current", description="Game patch version")
    include: List[str] = Field(
        default=["stats", "abilities"], description="Data sections to include"
    )

    @field_validator("include")
    @classmethod
    def validate_include_options(cls, v: List[str]) -> List[str]:
        valid_options = {"stats", "abilities", "builds", "history"}
        invalid = set(v) - valid_options
        if invalid:
            raise ValueError(f"Invalid include options: {invalid}")
        return v


# Response Models
class ChampionStats(BaseModel):
    """Champion comprehensive statistics model"""
    
    # Core stats
    health: Optional[float] = Field(None, description="Base health points")
    health_per_level: Optional[float] = Field(None, description="Health gained per level")
    mana: Optional[float] = Field(None, description="Base mana points")
    mana_per_level: Optional[float] = Field(None, description="Mana gained per level")
    attack_damage: Optional[float] = Field(None, description="Base attack damage")
    attack_damage_per_level: Optional[float] = Field(None, description="AD gained per level")
    armor: Optional[float] = Field(None, description="Base armor")
    armor_per_level: Optional[float] = Field(None, description="Armor gained per level")
    magic_resist: Optional[float] = Field(None, description="Base magic resistance")
    magic_resist_per_level: Optional[float] = Field(None, description="MR gained per level")
    movement_speed: Optional[float] = Field(None, description="Base movement speed")
    attack_range: Optional[float] = Field(None, description="Attack range")
    attack_speed: Optional[float] = Field(None, description="Base attack speed (attacks per second)")
    attack_speed_per_level: Optional[float] = Field(None, description="Attack speed gained per level")
    
    # Regeneration stats
    health_regen: Optional[float] = Field(None, description="Base health regeneration (HP5)")
    health_regen_per_level: Optional[float] = Field(None, description="HP5 gained per level")
    mana_regen: Optional[float] = Field(None, description="Base mana regeneration (MP5)")
    mana_regen_per_level: Optional[float] = Field(None, description="MP5 gained per level")
    
    # Critical and attack details
    critical_damage: Optional[float] = Field(None, description="Critical damage percentage")
    windup_percent: Optional[float] = Field(None, description="Attack windup percentage")
    attack_speed_ratio: Optional[float] = Field(None, description="Attack speed ratio")
    bonus_attack_speed: Optional[float] = Field(None, description="Bonus attack speed")
    base_attack_speed: Optional[float] = Field(None, description="Base attack speed (detailed)")
    
    # Missile and projectile
    missile_speed: Optional[float] = Field(None, description="Missile/projectile speed")
    
    # Unit radius data
    gameplay_radius: Optional[float] = Field(None, description="Gameplay radius for collision")
    selection_radius: Optional[float] = Field(None, description="Selection radius for clicking")
    pathing_radius: Optional[float] = Field(None, description="Pathing radius for movement")
    selection_height: Optional[float] = Field(None, description="Selection height for clicking")
    acquisition_radius: Optional[float] = Field(None, description="Acquisition radius for targeting")


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
    
    passive: Optional[AbilityInfo] = Field(None, description="Passive ability")
    q: Optional[AbilityInfo] = Field(None, description="Q ability")
    w: Optional[AbilityInfo] = Field(None, description="W ability")
    e: Optional[AbilityInfo] = Field(None, description="E ability")
    r: Optional[AbilityInfo] = Field(None, description="R (Ultimate) ability")


class ChampionData(BaseModel):
    """Complete champion data model"""
    
    name: str = Field(..., description="Champion name")
    title: str = Field(..., description="Champion title")
    roles: list[str] = Field(..., description="Primary roles")
    difficulty: Optional[int] = Field(None, ge=1, le=10, description="Difficulty rating 1-10")
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
    """Service class for champion data operations with WikiScraper integration"""
    
    def __init__(self, enable_wiki: bool = True, use_cache: bool = True):
        """
        Initialize the champion service with WikiScraper integration
        
        Args:
            enable_wiki: Whether to enable WikiScraper (disable for testing)
            use_cache: Whether to enable caching in WikiScraper
        """
        self.logger = structlog.get_logger(__name__)
        self.enable_wiki = enable_wiki
        self._mock_data = self._initialize_mock_data()
        self._stat_formulas = {}  # Store formulas for level calculations
        
        # Initialize WikiScraper if enabled
        if self.enable_wiki:
            self.wiki_scraper = WikiScraper(
                rate_limit_delay=1.0,
                timeout=30.0,
                max_retries=3,
                enable_cache=use_cache,
                cache_ttl_hours=24
            )
        else:
            self.wiki_scraper = None
            
        self.logger.info(
            "ChampionService initialized",
            wiki_enabled=self.enable_wiki,
            cache_enabled=use_cache
        )
    
    def _normalize_champion_name(self, name: str) -> str:
        """
        Normalize champion name for wiki lookup and internal processing
        
        Args:
            name: Champion name to normalize
            
        Returns:
            Normalized champion name
        """
        # Remove extra spaces and convert to title case
        normalized = name.strip().title()
        
        # Handle special characters for wiki compatibility
        # Examples: "Kai'Sa" -> "Kai'Sa", "Twisted Fate" -> "Twisted Fate"
        normalized = re.sub(r'\s+', ' ', normalized)  # Collapse multiple spaces
        
        self.logger.debug(f"Normalized champion name: {name} -> {normalized}")
        return normalized
    
    def _transform_wiki_stats(self, wiki_stats: Dict[str, Any]) -> Optional[ChampionStats]:
        """
        Transform WikiScraper stats format to ChampionStats model.
        Now supports complex formulas including quadratic growth.
        
        Args:
            wiki_stats: Stats from WikiScraper.parse_champion_stats()
            
        Returns:
            ChampionStats object with only available stats, or None if no stats available
        """
        if not wiki_stats:
            return None
            
        # Store formulas for later use
        self._stat_formulas = {}
            
        # Comprehensive mapping from WikiScraper field names to ChampionStats fields
        stat_mapping = {
            # Core stats
            'hp': ('health', 'health_per_level'),
            'mp': ('mana', 'mana_per_level'),
            'ad': ('attack_damage', 'attack_damage_per_level'),
            'armor': ('armor', 'armor_per_level'),
            'mr': ('magic_resist', 'magic_resist_per_level'),
            'attack_speed': ('attack_speed', 'attack_speed_per_level'),
            'movement_speed': ('movement_speed', None),
            'range': ('attack_range', None),
            
            # Regeneration stats
            'hp5': ('health_regen', 'health_regen_per_level'),
            'mp5': ('mana_regen', 'mana_regen_per_level'),
            
            # Critical and attack details
            'crit_damage': ('critical_damage', None),
            'windup_percent': ('windup_percent', None),
            'as_ratio': ('attack_speed_ratio', None),
            'bonus_as': ('bonus_attack_speed', None),
            'base_as': ('base_attack_speed', None),
            
            # Missile and projectile
            'missile_speed': ('missile_speed', None),
            
            # Unit radius data
            'gameplay_radius': ('gameplay_radius', None),
            'selection_radius': ('selection_radius', None),
            'pathing_radius': ('pathing_radius', None),
            'selection_height': ('selection_height', None),
            'acquisition_radius': ('acquisition_radius', None),
        }
        
        stats_data = {}
        stats_found = False
        
        for wiki_key, (base_field, growth_field) in stat_mapping.items():
            if wiki_key in wiki_stats:
                wiki_stat = wiki_stats[wiki_key]
                if isinstance(wiki_stat, dict):
                    # Store the formula if available for level calculations
                    if 'formula' in wiki_stat:
                        self._stat_formulas[base_field] = wiki_stat['formula']
                    
                    # Extract base value
                    if 'base' in wiki_stat:
                        stats_data[base_field] = float(wiki_stat['base'])
                        stats_found = True
                    
                    # Extract growth value if field exists
                    if growth_field and 'growth' in wiki_stat:
                        stats_data[growth_field] = float(wiki_stat['growth'])
                        stats_found = True
                    elif growth_field and 'growth_quadratic' in wiki_stat:
                        # Note: 'growth_quadratic' is actually linear growth (wiki notation was misleading)
                        linear_growth = float(wiki_stat['growth_quadratic'])
                        self.logger.info(f"Found linear growth (from M² notation) for {base_field}: {linear_growth}")
                        stats_data[growth_field] = linear_growth
                        stats_found = True
                else:
                    # Handle simple numeric values
                    stats_data[base_field] = float(wiki_stat)
                    stats_found = True
        
        if not stats_found:
            self.logger.warning("No usable stats found in wiki data")
            return None
        
        self.logger.info(f"Successfully transformed {len(stats_data)} stat fields from wiki")
        return ChampionStats(**stats_data)
    
    def calculate_stats_at_level(self, level: int) -> Optional[ChampionStats]:
        """
        Calculate champion stats at a specific level using stored formulas.
        
        Args:
            level: Champion level (1-18)
            
        Returns:
            ChampionStats object with values calculated for the specified level
        """
        if not 1 <= level <= 18:
            raise ValueError(f"Level must be between 1 and 18, got {level}")
        
        if not self._stat_formulas:
            self.logger.warning("No stat formulas available for level calculations")
            return None
        
        from src.utils.stat_calculator import StatCalculator
        
        # Calculate stats at the specified level
        calculated_stats = StatCalculator.calculate_stats_at_level(self._stat_formulas, level)
        
        # Create ChampionStats object with calculated values
        stats_data = {}
        
        # Map the calculated stats to ChampionStats fields
        stat_field_mapping = {
            'health': 'health',
            'mana': 'mana', 
            'attack_damage': 'attack_damage',
            'armor': 'armor',
            'magic_resist': 'magic_resist',
            'attack_speed': 'attack_speed',
            'movement_speed': 'movement_speed',
            'attack_range': 'attack_range'
        }
        
        for formula_key, calculated_value in calculated_stats.items():
            if formula_key in stat_field_mapping:
                stats_data[stat_field_mapping[formula_key]] = calculated_value
        
        self.logger.info(f"Calculated stats for level {level}: {len(stats_data)} stats")
        return ChampionStats(**stats_data)
    
    def get_stat_progression(self, start_level: int = 1, end_level: int = 18) -> Dict[int, ChampionStats]:
        """
        Get stat progression across multiple levels.
        
        Args:
            start_level: Starting level (default: 1)
            end_level: Ending level (default: 18)
            
        Returns:
            Dictionary mapping level to ChampionStats
        """
        if not self._stat_formulas:
            self.logger.warning("No stat formulas available for progression calculations")
            return {}
        
        progression = {}
        for level in range(start_level, end_level + 1):
            try:
                stats = self.calculate_stats_at_level(level)
                if stats:
                    progression[level] = stats
            except ValueError as e:
                self.logger.error(f"Failed to calculate stats for level {level}: {e}")
        
        return progression
    
    def _transform_wiki_abilities(self, wiki_abilities: Dict[str, Any]) -> Optional[ChampionAbilities]:
        """
        Transform WikiScraper abilities format to ChampionAbilities model
        Only includes abilities that are actually available from wiki
        
        Args:
            wiki_abilities: Abilities from WikiScraper.parse_champion_abilities()
            
        Returns:
            ChampionAbilities object with only available abilities, or None if no abilities available
        """
        if not wiki_abilities:
            return None
            
        def transform_ability(ability_data: Dict[str, Any]) -> AbilityInfo:
            """Transform single ability data"""
            # Format effects list into string
            effects = ability_data.get('effects', [])
            effect_str = ', '.join(effects) if effects else "No special effects"
            
            # Handle None values with appropriate defaults
            return AbilityInfo(
                name=ability_data.get('name', 'Unknown'),
                description=ability_data.get('description', 'No description available'),
                cooldown=ability_data.get('cooldown') or 'N/A',
                cost=ability_data.get('cost') or 'N/A',
                range=ability_data.get('range') or 'N/A',
                effect=effect_str
            )
        
        # Transform each ability - only include if we have data
        abilities_data = {}
        abilities_found = False
        
        ability_types = ['passive', 'Q', 'W', 'E', 'R']
        for ability_type in ability_types:
            key = ability_type.lower()
            if key in wiki_abilities:
                abilities_data[key] = transform_ability(wiki_abilities[key])
                abilities_found = True
            else:
                # Set to None for missing abilities instead of fake data
                abilities_data[key] = None
        
        if not abilities_found:
            self.logger.warning("No usable abilities found in wiki data")
            return None
        
        self.logger.info(f"Successfully transformed abilities from wiki")
        return ChampionAbilities(
            passive=abilities_data.get('passive'),
            q=abilities_data.get('q'),
            w=abilities_data.get('w'), 
            e=abilities_data.get('e'),
            r=abilities_data.get('r')
        )
    
    async def _get_champion_from_wiki(self, champion_name: str) -> ChampionData:
        """
        Get champion data from WikiScraper
        
        Args:
            champion_name: Champion name to fetch
            
        Returns:
            ChampionData object with real wiki data (stats/abilities may be None if unavailable)
            
        Raises:
            WikiScraperError: If wiki scraping fails
            ChampionNotFoundError: If champion not found on wiki
        """
        if not self.wiki_scraper:
            raise WikiScraperError("WikiScraper not enabled")
        
        normalized_name = self._normalize_champion_name(champion_name)
        
        self.logger.info(f"Fetching champion data from wiki: {normalized_name}")
        
        # Fetch and parse the champion page
        soup = await self.wiki_scraper.fetch_champion_page(normalized_name)
        
        # Parse comprehensive stats and abilities safely
        wiki_stats = self.wiki_scraper.parse_comprehensive_champion_stats_safe(soup)
        wiki_abilities = self.wiki_scraper.parse_champion_abilities_safe(soup)
        
        # Transform to ChampionData format (may be None if no data available)
        stats = None
        abilities = None
        
        # Simplified error handling: Check for error key, then extract data appropriately
        if 'error' not in wiki_stats and wiki_stats:
            # Success case - stats is the dict itself
            stats = self._transform_wiki_stats(wiki_stats)
        elif wiki_stats.get('stats'):
            # Failure case - empty stats dict wrapped under 'stats' key
            # Only transform if there's actual data, not just an empty dict
            if wiki_stats['stats']:
                stats = self._transform_wiki_stats(wiki_stats['stats'])
            
        if 'error' not in wiki_abilities and wiki_abilities.get('abilities'):
            # Success case - abilities dict is directly in the result
            abilities = self._transform_wiki_abilities(wiki_abilities['abilities'])
        elif wiki_abilities.get('abilities'):
            # Failure case - empty abilities dict wrapped under 'abilities' key
            # Only transform if there's actual data, not just an empty dict
            if wiki_abilities['abilities']:
                abilities = self._transform_wiki_abilities(wiki_abilities['abilities'])
        
        # Create ChampionData object
        champion_data = ChampionData(
            name=normalized_name,
            title="Champion from Wiki",  # Generic title - will be enhanced in future tasks
            roles=["Unknown"],  # Will be enhanced in future tasks
            difficulty=None,  # Don't fake difficulty if we don't have it
            stats=stats,  # May be None
            abilities=abilities,  # May be None
            tags=["Champion"],  # Will be enhanced in future tasks
            patch="current"
        )
        
        # Log what we actually got
        stats_status = "available" if stats else "unavailable"
        abilities_status = "available" if abilities else "unavailable"
        self.logger.info(
            f"Retrieved wiki data for {normalized_name}",
            stats=stats_status,
            abilities=abilities_status
        )
        
        return champion_data
    
    async def _get_champion_from_mock(self, champion_name: str) -> ChampionData:
        """
        Get champion data from mock data (refactored from existing code)
        
        Args:
            champion_name: Champion name to fetch
            
        Returns:
            ChampionData object with mock data
            
        Raises:
            ChampionNotFoundError: If champion not found in mock data
        """
        champion_key = champion_name.lower().strip()
        
        if champion_key not in self._mock_data:
            raise ChampionNotFoundError(champion_name)
        
        return self._mock_data[champion_key]

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
        include: Optional[list[str]] = None
    ) -> Dict[str, Any]:
        """
        Retrieve comprehensive champion data with WikiScraper integration and fallback
        
        Args:
            champion: Champion name to retrieve data for
            patch: Game patch version (default: "current")
            include: List of data sections to include (stats, abilities, builds, history)
            
        Returns:
            Dictionary containing champion data based on include parameters
            
        Raises:
            ChampionNotFoundError: If champion is not found in any data source
            ValidationError: If input parameters are invalid
        """
        # Log the request
        self.logger.info(
            "Champion data request",
            champion=champion,
            patch=patch,
            include=include,
            wiki_enabled=self.enable_wiki
        )
        
        try:
            # Validate input using Pydantic model
            validated_input = GetChampionDataInput(
                champion=champion,
                patch=patch,
                include=include
            )
            
            # Try to get data from WikiScraper first, then fallback to mock
            champion_data = None
            data_source = "unknown"
            
            if self.enable_wiki:
                try:
                    wiki_data = await self._get_champion_from_wiki(champion)
                    
                    # Check if we got useful data from wiki
                    has_useful_data = False
                    if ("stats" in include and wiki_data.stats) or ("abilities" in include and wiki_data.abilities):
                        has_useful_data = True
                    elif "stats" not in include and "abilities" not in include:
                        # If not requesting stats/abilities, wiki data is useful
                        has_useful_data = True
                    
                    if has_useful_data:
                        champion_data = wiki_data
                        data_source = "wiki"
                        self.logger.info(f"Retrieved {champion} data from wiki with useful content")
                    else:
                        # Wiki page exists but no useful data - fallback to mock
                        self.logger.warning(f"Wiki data for {champion} incomplete, falling back to mock data")
                        champion_data = await self._get_champion_from_mock(champion)
                        data_source = "mock_fallback_incomplete"
                        
                except (WikiScraperError, WikiChampionNotFoundError, httpx.RequestError, Exception) as e:
                    self.logger.warning(
                        f"Wiki failed for {champion}, falling back to mock data: {e}",
                        error_type=type(e).__name__
                    )
                    champion_data = await self._get_champion_from_mock(champion)
                    data_source = "mock_fallback_error"
            else:
                champion_data = await self._get_champion_from_mock(champion)
                data_source = "mock"
                
            # Build response based on include parameters
            response = {
                "name": champion_data.name,
                "title": champion_data.title,
                "roles": champion_data.roles,
                "difficulty": champion_data.difficulty,
                "tags": champion_data.tags,
                "patch": champion_data.patch,
                "data_source": data_source,  # Track which source was used
                "data_included": validated_input.include
            }
            
            # Add requested data sections
            if "stats" in validated_input.include:
                if champion_data.stats:
                    response["stats"] = champion_data.stats.model_dump()
                else:
                    response["stats"] = None
                    # Note: Removed debug notes for cleaner production API responses
            
            if "abilities" in validated_input.include:
                if champion_data.abilities:
                    response["abilities"] = champion_data.abilities.model_dump()
                else:
                    response["abilities"] = None
                    # Note: Removed debug notes for cleaner production API responses
            
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
                data_source=data_source,
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
                error_type=type(e).__name__,
            )
            raise
    
    async def cleanup(self):
        """Cleanup resources (WikiScraper, etc.)"""
        if self.wiki_scraper:
            await self.wiki_scraper.close()
            self.logger.info("WikiScraper resources cleaned up")
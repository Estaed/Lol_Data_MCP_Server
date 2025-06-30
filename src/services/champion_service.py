"""
Champion Service for League of Legends MCP Server (Updated with WikiScraper Integration)

This module provides service layer functionality for retrieving and processing
champion data. It handles data validation, error handling, and logging for
champion-related operations with real wiki data and mock fallback.
"""

import logging
import re
import httpx
from typing import Dict, Any, Optional
import structlog

from pydantic import BaseModel, Field, ValidationError
from src.mcp_server.tools import GetChampionDataInput
from src.data_sources.scrapers.wiki_scraper import WikiScraper, WikiScraperError, ChampionNotFoundError as WikiChampionNotFoundError


# Response Models
class ChampionStats(BaseModel):
    """Champion base statistics model"""
    
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
        Transform WikiScraper stats format to ChampionStats model
        Only includes stats that are actually available from wiki - no fake defaults
        
        Args:
            wiki_stats: Stats from WikiScraper.parse_champion_stats()
            
        Returns:
            ChampionStats object with only available stats, or None if no stats available
        """
        if not wiki_stats:
            return None
            
        # Mapping from WikiScraper field names to ChampionStats fields
        stat_mapping = {
            'hp': ('health', 'health_per_level'),
            'mp': ('mana', 'mana_per_level'),
            'ad': ('attack_damage', 'attack_damage_per_level'),
            'armor': ('armor', 'armor_per_level'),
            'mr': ('magic_resist', 'magic_resist_per_level'),
            'attack_speed': ('attack_speed', 'attack_speed_per_level'),
            'movement_speed': ('movement_speed', None),
            'attack_range': ('attack_range', None)
        }
        
        stats_data = {}
        stats_found = False
        
        for wiki_key, (base_field, growth_field) in stat_mapping.items():
            if wiki_key in wiki_stats:
                wiki_stat = wiki_stats[wiki_key]
                if isinstance(wiki_stat, dict):
                    # Extract base value
                    if 'base' in wiki_stat:
                        stats_data[base_field] = float(wiki_stat['base'])
                        stats_found = True
                    
                    # Extract growth value if field exists
                    if growth_field and 'growth' in wiki_stat:
                        stats_data[growth_field] = float(wiki_stat['growth'])
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
        
        # Parse stats and abilities safely
        wiki_stats = self.wiki_scraper.parse_champion_stats_safe(soup)
        wiki_abilities = self.wiki_scraper.parse_champion_abilities_safe(soup)
        
        # Transform to ChampionData format (may be None if no data available)
        stats = None
        abilities = None
        
        if wiki_stats.get('stats'):
            stats = self._transform_wiki_stats(wiki_stats['stats'])
            
        if wiki_abilities.get('abilities'):
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
        if include is None:
            include = ["stats", "abilities"]
        
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
                    response["stats_note"] = "Stats not available from data source"
            
            if "abilities" in validated_input.include:
                if champion_data.abilities:
                    response["abilities"] = champion_data.abilities.model_dump()
                else:
                    response["abilities"] = None
                    response["abilities_note"] = "Abilities not available from data source"
            
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
        Check if a champion exists using wiki validation with fallback to mock data
        
        Args:
            champion: Champion name to check
            
        Returns:
            True if champion exists, False otherwise
        """
        if self.enable_wiki and self.wiki_scraper:
            try:
                # Use wiki validation for real champion checking
                exists = await self.wiki_scraper.validate_champion_exists(champion)
                if exists:
                    self.logger.debug(f"Champion {champion} validated via wiki")
                    return True
                else:
                    # Fallback to mock data if not found in wiki
                    normalized_name = self._normalize_champion_name(champion)
                    mock_exists = normalized_name.lower() in self._mock_data
                    if mock_exists:
                        self.logger.debug(f"Champion {champion} found in mock data as fallback")
                    return mock_exists
            except Exception as e:
                self.logger.warning(f"Wiki validation failed for {champion}: {e}, checking mock data")
                # Fallback to mock data on error
                normalized_name = self._normalize_champion_name(champion)
                return normalized_name.lower() in self._mock_data
        else:
            # Wiki disabled, use mock data only
            normalized_name = self._normalize_champion_name(champion)
            return normalized_name.lower() in self._mock_data

    async def discover_champions(self, force_refresh: bool = False) -> list[str]:
        """
        Discover all available champions from wiki or mock data
        
        Args:
            force_refresh: If True, bypass cache and fetch fresh data
            
        Returns:
            List of champion names
        """
        if self.enable_wiki and self.wiki_scraper:
            try:
                wiki_champions = await self.wiki_scraper.discover_champions(force_refresh)
                self.logger.info(f"Discovered {len(wiki_champions)} champions from wiki")
                return wiki_champions
            except Exception as e:
                self.logger.warning(f"Wiki champion discovery failed: {e}, using mock data")
                return self.get_available_champions()
        else:
            return self.get_available_champions()

    async def search_champions(self, query: str, limit: int = 10) -> list[str]:
        """
        Search for champions by partial name matching
        
        Args:
            query: Search query (partial champion name)
            limit: Maximum number of results to return
            
        Returns:
            List of matching champion names
        """
        if not query or len(query) < 2:
            return []
        
        if self.enable_wiki and self.wiki_scraper:
            try:
                # Get all champions from wiki and search them
                all_champions = await self.wiki_scraper.discover_champions()
                results = self._search_champion_list(query, all_champions, limit)
                self.logger.debug(f"Found {len(results)} champions matching '{query}' via wiki")
                return results
            except Exception as e:
                self.logger.warning(f"Wiki champion search failed: {e}, using mock data")
                # Fallback to mock data search
                return self._search_mock_champions(query, limit)
        else:
            return self._search_mock_champions(query, limit)

    def _search_champion_list(self, query: str, champions: list[str], limit: int = 10) -> list[str]:
        """
        Search a list of champions for partial matches
        
        Args:
            query: Search query
            champions: List of champion names to search
            limit: Maximum results
            
        Returns:
            List of matching champion names
        """
        if not query or len(query) < 2:
            return []
        
        query_lower = query.lower().strip()
        matches = []
        
        for champion_name in champions:
            score = self._calculate_match_score(query_lower, champion_name.lower())
            if score > 0:
                matches.append((champion_name, score))
        
        # Sort by score (descending) and return top results
        matches.sort(key=lambda x: x[1], reverse=True)
        return [match[0] for match in matches[:limit]]

    def _search_mock_champions(self, query: str, limit: int = 10) -> list[str]:
        """
        Search mock champions for partial matches
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of matching champion names
        """
        mock_champion_names = [self._mock_data[key].name for key in self._mock_data.keys()]
        return self._search_champion_list(query, mock_champion_names, limit)

    def _calculate_match_score(self, query: str, champion_name: str) -> float:
        """
        Calculate match score for champion search
        
        Args:
            query: Search query (lowercase)
            champion_name: Champion name (lowercase)
            
        Returns:
            Match score (higher is better, 0 means no match)
        """
        if not query or not champion_name:
            return 0.0
        
        # Exact match gets highest score
        if query == champion_name:
            return 100.0
        
        # Starts with query gets high score
        if champion_name.startswith(query):
            return 90.0 - len(champion_name) * 0.1  # Prefer shorter names
        
        # Contains query gets medium score
        if query in champion_name:
            # Higher score for earlier position
            position = champion_name.find(query)
            return 50.0 - position * 2.0
        
        # Word-based matching for multi-word champions
        words = champion_name.split()
        for word in words:
            if word.startswith(query[:min(len(query), 3)]):
                return 30.0
        
        return 0.0
    
    async def cleanup(self):
        """Cleanup resources (WikiScraper, etc.)"""
        if self.wiki_scraper:
            await self.wiki_scraper.close()
            self.logger.info("WikiScraper resources cleaned up")
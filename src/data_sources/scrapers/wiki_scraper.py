"""
League of Legends Wiki Scraper

A comprehensive web scraper for extracting champion data from the League of Legends Wiki.
Implements rate limiting, error handling, and proper HTTP client configuration.
"""

import asyncio
import json
import hashlib
import logging
import os
import re
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from urllib.parse import urljoin, quote

import httpx
from bs4 import BeautifulSoup, Tag


class WikiScraperError(Exception):
    """Base exception for wiki scraper errors"""
    pass


class ChampionNotFoundError(WikiScraperError):
    """Raised when a champion page cannot be found"""
    pass


@dataclass
class ScrapingMetrics:
    """Performance metrics for scraping operations"""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    parsing_successes: int = 0
    parsing_failures: int = 0
    total_request_time: float = 0.0
    avg_request_time: float = 0.0
    errors: List[str] = field(default_factory=list)


class CacheManager:
    """Manages file-based caching for scraped pages"""
    
    def __init__(self, cache_dir: str = "cache/wiki_pages", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.ttl = timedelta(hours=ttl_hours)
        self.metadata_file = self.cache_dir / "metadata.json"
        self.logger = logging.getLogger(__name__)
        self._ensure_cache_dir()
        
    def _ensure_cache_dir(self) -> None:
        """Create cache directory if it doesn't exist"""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Cache directory ensured: {self.cache_dir}")
        except OSError as e:
            self.logger.error(f"Failed to create cache directory: {e}")
            
    def _get_cache_key(self, champion_name: str) -> str:
        """Generate cache key for champion"""
        return hashlib.md5(champion_name.lower().encode()).hexdigest()
        
    def _load_metadata(self) -> Dict[str, Any]:
        """Load cache metadata"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                self.logger.warning(f"Failed to load cache metadata: {e}")
                return {}
        return {}
        
    def _save_metadata(self, metadata: Dict[str, Any]) -> None:
        """Save cache metadata"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, default=str)
        except IOError as e:
            self.logger.warning(f"Failed to save cache metadata: {e}")
            
    def is_cache_valid(self, champion_name: str) -> bool:
        """Check if cached data is still valid"""
        cache_key = self._get_cache_key(champion_name)
        cache_file = self.cache_dir / f"{cache_key}.html"
        
        if not cache_file.exists():
            return False
            
        metadata = self._load_metadata()
        if cache_key not in metadata:
            return False
            
        try:
            cached_time = datetime.fromisoformat(metadata[cache_key]['timestamp'])
            is_valid = datetime.now() - cached_time < self.ttl
            self.logger.debug(f"Cache validity check for {champion_name}: {is_valid}")
            return is_valid
        except (KeyError, ValueError) as e:
            self.logger.warning(f"Invalid cache metadata for {champion_name}: {e}")
            return False
        
    def get_cached_content(self, champion_name: str) -> Optional[str]:
        """Get cached HTML content if valid"""
        if not self.is_cache_valid(champion_name):
            return None
            
        cache_key = self._get_cache_key(champion_name)
        cache_file = self.cache_dir / f"{cache_key}.html"
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                content = f.read()
                self.logger.debug(f"Retrieved cached content for {champion_name} ({len(content)} chars)")
                return content
        except IOError as e:
            self.logger.warning(f"Failed to read cached content for {champion_name}: {e}")
            return None
            
    def cache_content(self, champion_name: str, content: str) -> None:
        """Cache HTML content"""
        cache_key = self._get_cache_key(champion_name)
        cache_file = self.cache_dir / f"{cache_key}.html"
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                f.write(content)
                
            metadata = self._load_metadata()
            metadata[cache_key] = {
                'champion_name': champion_name,
                'timestamp': datetime.now().isoformat(),
                'file_size': len(content)
            }
            self._save_metadata(metadata)
            self.logger.info(f"Cached content for {champion_name} ({len(content)} chars)")
        except IOError as e:
            self.logger.warning(f"Failed to cache content for {champion_name}: {e}")
            
    def cleanup_expired(self) -> int:
        """Remove expired cache entries"""
        metadata = self._load_metadata()
        removed_count = 0
        
        for cache_key, data in list(metadata.items()):
            try:
                cached_time = datetime.fromisoformat(data['timestamp'])
                if datetime.now() - cached_time >= self.ttl:
                    cache_file = self.cache_dir / f"{cache_key}.html"
                    try:
                        cache_file.unlink(missing_ok=True)
                        del metadata[cache_key]
                        removed_count += 1
                        self.logger.debug(f"Removed expired cache entry: {cache_key}")
                    except IOError as e:
                        self.logger.warning(f"Failed to remove cache file {cache_key}: {e}")
            except (KeyError, ValueError) as e:
                self.logger.warning(f"Invalid cache entry {cache_key}: {e}")
                
        if removed_count > 0:
            self._save_metadata(metadata)
            self.logger.info(f"Cleaned up {removed_count} expired cache entries")
            
        return removed_count


class WikiScraper:
    """
    League of Legends Wiki scraper with rate limiting and error handling.
    
    Features:
    - Rate limiting (1 request per second)
    - Proper HTTP headers and user agent
    - Connection timeout and retry logic
    - Basic logging for scraper operations
    - LoL Wiki URL handling
    """
    
    BASE_URL = "https://wiki.leagueoflegends.com/en-us"
    CHAMPION_URL_TEMPLATE = "/{champion_name}"
    
    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        enable_cache: bool = True,
        cache_ttl_hours: int = 24
    ):
        """
        Initialize the WikiScraper.
        
        Args:
            rate_limit_delay: Delay between requests in seconds (default: 1.0)
            timeout: HTTP request timeout in seconds (default: 30.0)
            max_retries: Maximum number of retry attempts (default: 3)
            retry_delay: Delay between retries in seconds (default: 2.0)
            enable_cache: Enable file-based caching (default: True)
            cache_ttl_hours: Cache time-to-live in hours (default: 24)
        """
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.last_request_time = 0.0
        
        # Configure caching and metrics
        self.enable_cache = enable_cache
        self.cache_manager = CacheManager(ttl_hours=cache_ttl_hours) if enable_cache else None
        self.metrics = ScrapingMetrics()
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
        
        # HTTP client configuration
        self.headers = {
            "User-Agent": (
                "LoL-Data-MCP-Server/1.0 "
                "(https://github.com/user/lol-data-mcp-server) "
                "Educational Research Bot"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        
        # HTTP client (will be created when needed)
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self) -> 'WikiScraper':
        """Async context manager entry"""
        await self._ensure_client()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit"""
        await self.close()
    
    async def _ensure_client(self) -> None:
        """Ensure HTTP client is initialized"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=self.headers,
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True
            )
            self.logger.info("HTTP client initialized")
    
    async def close(self) -> None:
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
            self.logger.info("HTTP client closed")
    
    def _update_metrics(self, start_time: float, success: bool, cache_hit: bool = False, error: Optional[str] = None) -> None:
        """Update performance metrics"""
        request_time = time.time() - start_time
        self.metrics.total_requests += 1
        self.metrics.total_request_time += request_time
        self.metrics.avg_request_time = self.metrics.total_request_time / self.metrics.total_requests
        
        if success:
            self.metrics.parsing_successes += 1
        else:
            self.metrics.parsing_failures += 1
            if error:
                error_entry = f"{datetime.now().isoformat()}: {error}"
                self.metrics.errors.append(error_entry)
                
        self.logger.debug(f"Updated metrics: requests={self.metrics.total_requests}, "
                         f"successes={self.metrics.parsing_successes}, "
                         f"cache_hits={self.metrics.cache_hits}, "
                         f"avg_time={self.metrics.avg_request_time:.3f}s")
    
    async def _rate_limit(self) -> None:
        """Implement rate limiting to respect server resources"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            self.logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _build_champion_url(self, champion_name: str) -> str:
        """
        Build a properly formatted champion URL for the LoL Wiki.
        
        Args:
            champion_name: Name of the champion (e.g., "Taric", "Kai'Sa")
            
        Returns:
            Full URL to the champion's wiki page
        """
        # Handle special characters and formatting
        formatted_name = champion_name.replace("'", "'").replace(" ", "_")
        champion_path = self.CHAMPION_URL_TEMPLATE.format(champion_name=quote(formatted_name))
        url = urljoin(self.BASE_URL, champion_path)
        
        self.logger.debug(f"Built champion URL: {url}")
        return url
    
    async def _make_request(self, url: str) -> httpx.Response:
        """
        Make an HTTP request with retry logic and rate limiting.
        
        Args:
            url: URL to request
            
        Returns:
            HTTP response object
            
        Raises:
            WikiScraperError: If request fails after all retries
        """
        await self._ensure_client()
        await self._rate_limit()
        
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                self.logger.debug(f"Making request to {url} (attempt {attempt + 1})")
                if self._client is None:
                    raise WikiScraperError("HTTP client is not initialized")
                response = await self._client.get(url)
                
                                 # Check for success status codes
                if response is not None and response.status_code == 200:
                    self.logger.info(f"Successfully fetched {url}")
                    return response
                elif response is not None and response.status_code == 404:
                    raise ChampionNotFoundError(f"Champion page not found: {url}")
                elif response is not None:
                    response.raise_for_status()
                    
            except httpx.HTTPError as e:
                last_exception = e
                if attempt < self.max_retries:
                    retry_delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    self.logger.warning(
                        f"Request failed (attempt {attempt + 1}): {e}. "
                        f"Retrying in {retry_delay:.2f} seconds..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    self.logger.error(f"Request failed after {self.max_retries + 1} attempts: {e}")
        
        raise WikiScraperError(f"Failed to fetch {url} after {self.max_retries + 1} attempts") from last_exception
    
    async def fetch_champion_page(self, champion_name: str) -> BeautifulSoup:
        """
        Fetch and parse a champion's wiki page with caching support.
        
        Args:
            champion_name: Name of the champion (e.g., "Taric")
            
        Returns:
            BeautifulSoup object containing the parsed HTML
            
        Raises:
            ChampionNotFoundError: If champion page doesn't exist
            WikiScraperError: If page cannot be fetched
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Fetching champion page for: {champion_name}")
            
            # Check cache first
            if self.enable_cache and self.cache_manager:
                cached_content = self.cache_manager.get_cached_content(champion_name)
                if cached_content:
                    self.metrics.cache_hits += 1
                    self.logger.info(f"Cache hit for champion: {champion_name}")
                    soup = BeautifulSoup(cached_content, 'html.parser')
                    self._update_metrics(start_time, success=True, cache_hit=True)
                    return soup
                else:
                    self.metrics.cache_misses += 1
                    self.logger.debug(f"Cache miss for champion: {champion_name}")
            
            # Fetch from web
            url = self._build_champion_url(champion_name)
            response = await self._make_request(url)
            content = response.text
            
            # Cache the content
            if self.enable_cache and self.cache_manager:
                self.cache_manager.cache_content(champion_name, content)
                
            soup = BeautifulSoup(content, 'html.parser')
            
            # Basic validation that we got a champion page
            title = soup.find('title')
            if title is not None:
                title_text = title.get_text()
                if 'League of Legends Wiki' not in title_text:
                    self.logger.warning(f"Unusual page title: {title_text}")
            
            self.logger.info(f"Successfully parsed champion page for {champion_name}")
            self._update_metrics(start_time, success=True, cache_hit=False)
            
            return soup
            
        except Exception as e:
            self._update_metrics(start_time, success=False, error=str(e))
            self.logger.error(f"Failed to fetch champion page for {champion_name}: {e}")
            raise
    
    async def test_connection(self) -> bool:
        """
        Test connection to the LoL Wiki.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Test connection using the base URL
            response = await self._make_request(self.BASE_URL)
            self.logger.info("Wiki connection test successful")
            return True
        except Exception as e:
            self.logger.error(f"Wiki connection test failed: {e}")
            return False

    def find_champion_data_sections(self, soup: BeautifulSoup) -> Dict[str, Optional[Tag]]:
        """
        Find and identify different data sections on a champion page.
        
        Args:
            soup: BeautifulSoup object of the champion page
            
        Returns:
            Dictionary mapping section names to BeautifulSoup elements:
            - 'stats': Champion statistics section (infobox)
            - 'abilities': Abilities section 
            - 'overview': General champion overview
            None values indicate missing sections
        """
        self.logger.info("Finding champion data sections")
        
        sections = {
            'stats': self._find_stats_section(soup),
            'abilities': self._find_abilities_section(soup),
            'overview': self._find_overview_section(soup)
        }
        
        # Log what was found
        found_sections = [name for name, section in sections.items() if section is not None]
        missing_sections = [name for name, section in sections.items() if section is None]
        
        self.logger.info(f"Found sections: {found_sections}")
        if missing_sections:
            self.logger.warning(f"Missing sections: {missing_sections}")
            
        return sections
    
    def _find_stats_section(self, soup: BeautifulSoup) -> Optional[Tag]:
        """
        Find the champion stats infobox section.
        
        Args:
            soup: BeautifulSoup object of the champion page
            
        Returns:
            BeautifulSoup element containing stats, or None if not found
        """
        self.logger.debug("Looking for stats section")
        
        # Primary approach: Look for infobox with champion stats class
        def has_stats_classes(class_list: Any) -> bool:
            """Check if element has champion stats related classes"""
            if not class_list:
                return False
            
            stats_indicators = [
                'infobox', 'champion-stats', 'stats', 'champion-info', 
                'character-info', 'data-box'
            ]
            
            class_string = ' '.join(class_list).lower()
            return any(indicator in class_string for indicator in stats_indicators)
        
        stats_infobox = soup.find('div', class_=has_stats_classes)
        
        if stats_infobox and isinstance(stats_infobox, Tag):
            self.logger.debug("Found stats section via type-champion-stats infobox")
            return stats_infobox
        
        # Fallback 1: Look for any infobox containing stat-like content
        infoboxes = soup.find_all('div', class_='infobox')
        for infobox in infoboxes:
            if isinstance(infobox, Tag):
                text = infobox.get_text().lower()
                # Check for common stat abbreviations
                if any(stat in text for stat in ['hp', 'mp', 'ar', 'ad', 'mr', 'attack damage']):
                    self.logger.debug("Found stats section via infobox content analysis")
                    return infobox
        
        # Fallback 2: Look for tables containing stats
        tables = soup.find_all('table')
        for table in tables:
            if isinstance(table, Tag):
                text = table.get_text().lower()
                if 'base statistics' in text or 'champion stats' in text:
                    self.logger.debug("Found stats section via table content")
                    return table
        
        self.logger.warning("Could not find stats section")
        return None
    
    def _find_abilities_section(self, soup: BeautifulSoup) -> Optional[Tag]:
        """
        Find the abilities section on the champion page.
        
        Args:
            soup: BeautifulSoup object of the champion page
            
        Returns:
            BeautifulSoup element containing abilities, or None if not found
        """
        self.logger.debug("Looking for abilities section")
        
        # Primary approach: Look for "Abilities" heading and get following content
        def contains_ability(text: str) -> bool:
            """Check if text contains ability-related keywords"""
            if not text:
                return False
            
            text_lower = text.lower()
            ability_keywords = [
                'abilities', 'skills', 'spells', 'passive', 'active',
                'cooldown', 'mana cost', 'damage', 'cast', 'ability'
            ]
            
            return any(keyword in text_lower for keyword in ability_keywords)
        
        abilities_span = soup.find('span', class_='mw-headline', string=contains_ability)
        
        if abilities_span and isinstance(abilities_span, Tag):
            # Find the parent heading element
            heading = abilities_span.find_parent(['h1', 'h2', 'h3', 'h4'])
            if heading and isinstance(heading, Tag):
                # Get the section after this heading until the next heading
                section_content = []
                current = heading.next_sibling
                
                while current:
                    if isinstance(current, Tag) and current.name in ['h1', 'h2', 'h3', 'h4']:
                        # Stop at next heading of same or higher level
                        break
                    if isinstance(current, Tag):
                        section_content.append(current)
                    current = current.next_sibling
                
                if section_content:
                    self.logger.debug("Found abilities section via mw-headline")
                    # Create a wrapper div containing all abilities content
                    wrapper = soup.new_tag('div')
                    wrapper['class'] = 'abilities-section'
                    for element in section_content:
                        wrapper.append(element.extract())
                    return wrapper
        
        # Fallback 1: Look for any heading containing "ability"
        ability_headers = soup.find_all(['h1', 'h2', 'h3', 'h4'])
        
        for header in ability_headers:
            if isinstance(header, Tag) and header.string and 'abilit' in header.string.lower():
                # Get content after this header
                content = []
                current = header.next_sibling
                while current and not (isinstance(current, Tag) and current.name in ['h1', 'h2', 'h3']):
                    if isinstance(current, Tag):
                        content.append(current)
                    current = current.next_sibling
                
                if content:
                    self.logger.debug("Found abilities section via header search")
                    wrapper = soup.new_tag('div')
                    wrapper['class'] = 'abilities-section-fallback'
                    for element in content:
                        wrapper.append(element.extract())
                    return wrapper
        
        # Fallback 2: Look for divs/sections with ability-related classes or content
        def has_ability_classes(class_list) -> bool:
            """Check if element has ability-related classes"""
            if not class_list:
                return False
            
            ability_indicators = [
                'ability', 'skill', 'spell', 'abilities', 'champion-abilities'
            ]
            
            class_string = ' '.join(class_list).lower()
            return any(indicator in class_string for indicator in ability_indicators)
        
        ability_divs = soup.find_all('div', class_=has_ability_classes)
        
        if ability_divs:
            for div in ability_divs:
                if isinstance(div, Tag):
                    self.logger.debug("Found abilities section via class-based search")
                    return div
        
        self.logger.warning("Could not find abilities section")
        return None
    
    def _find_overview_section(self, soup: BeautifulSoup) -> Optional[Tag]:
        """
        Find the champion overview/summary section.
        
        Args:
            soup: BeautifulSoup object of the champion page
            
        Returns:
            BeautifulSoup element containing overview, or None if not found
        """
        self.logger.debug("Looking for overview section")
        
        # Look for champion description/overview paragraphs near the top
        # Usually the first few paragraphs after the infobox
        main_content = soup.find('div', {'id': 'mw-content-text'})
        if main_content and isinstance(main_content, Tag):
            # Find first substantial paragraph
            paragraphs = main_content.find_all('p')
            for p in paragraphs:
                if isinstance(p, Tag):
                    text = p.get_text().strip()
                    if len(text) > 50:  # Substantial content
                        self.logger.debug("Found overview section via first substantial paragraph")
                        return p
        
        # Fallback: look for any div with summary/description content
        def has_summary_classes(class_list) -> bool:
            """Check if element has summary/overview related classes"""
            if not class_list:
                return False
            
            summary_indicators = [
                'summary', 'overview', 'description', 'champion-description',
                'intro', 'character-summary'
            ]
            
            class_string = ' '.join(class_list).lower()
            return any(indicator in class_string for indicator in summary_indicators)
        
        summary_divs = soup.find_all('div', class_=has_summary_classes)
        
        if summary_divs:
            for div in summary_divs:
                if isinstance(div, Tag):
                    self.logger.debug("Found overview section via class-based search")
                    return div
        
        self.logger.debug("No specific overview section found")
        return None
    
    def parse_champion_stats(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Parse champion statistics from the stats section of a champion page.
        
        Extracts base stats and per-level growth for:
        - HP (Health Points)
        - MP (Mana Points) 
        - AD (Attack Damage)
        - AS (Attack Speed)
        - AR (Armor)
        - MR (Magic Resistance)
        - MS (Movement Speed)
        - Range (Attack Range)
        
        Args:
            soup: BeautifulSoup object of the champion page
            
        Returns:
            Dictionary containing structured champion stats:
            {
                "hp": {"base": 645.0, "growth": 99.0},
                "mp": {"base": 300.0, "growth": 60.0},
                "ad": {"base": 55.0, "growth": 3.5},
                ...
            }
            
        Raises:
            WikiScraperError: If stats section cannot be found or parsed
        """
        self.logger.info("Parsing champion statistics")
        
        # Find the stats section
        stats_section = self._find_stats_section(soup)
        if not stats_section:
            raise WikiScraperError("Could not find stats section for parsing")
        
        # Extract all text content from the stats section
        stats_text = stats_section.get_text()
        self.logger.debug(f"Stats section text: {stats_text[:200]}...")
        
        # Initialize stats dictionary
        parsed_stats = {}
        
        # Define stat patterns and their variations
        stat_patterns = {
            'hp': ['hp', 'health', 'health points'],
            'mp': ['mp', 'mana', 'mana points'],
            'ad': ['ad', 'attack damage', 'attack dmg', 'damage'],
            'armor': ['ar', 'armor', 'armour'],
            'mr': ['mr', 'magic resistance', 'magic resist', 'magic res'],
            'attack_speed': ['as', 'attack speed', 'attackspeed'],
            'movement_speed': ['ms', 'movement speed', 'movespeed', 'move speed'],
            'range': ['range', 'attack range', 'atk range']
        }
        
        # Parse each stat type
        for stat_key, stat_names in stat_patterns.items():
            stat_data = self._extract_stat_value(stats_text, stat_names)
            if stat_data:
                parsed_stats[stat_key] = stat_data
                self.logger.debug(f"Parsed {stat_key}: {stat_data}")
        
        # Validate parsed data
        validated_stats = self._validate_stat_data(parsed_stats)
        
        self.logger.info(f"Successfully parsed {len(validated_stats)} champion stats")
        return validated_stats

    def _extract_stat_value(self, text: str, stat_names: list) -> Optional[Dict[str, float]]:
        """
        Extract base and growth values for a specific stat from text.
        
        Handles formats like:
        - "HP: 645 (+99)"
        - "Attack Damage: 55 (+3.5 per level)"
        - "Movement Speed: 340"
        - "Attack Speed: 0.625 (+2.14%)"
        
        Args:
            text: Text content to search
            stat_names: List of possible names for this stat
            
        Returns:
            Dictionary with 'base' and optionally 'growth' values, or None if not found
        """
        text_lower = text.lower()
        
        for stat_name in stat_names:
            # Create regex pattern for this stat name
            # Pattern matches: "StatName: 123.45 (+67.89)" or "StatName: 123.45"
            pattern = rf'{re.escape(stat_name.lower())}\s*:?\s*([0-9]+\.?[0-9]*)\s*(?:\(\+([0-9]+\.?[0-9]*)[^)]*\))?'
            
            match = re.search(pattern, text_lower)
            if match:
                try:
                    base_value = float(match.group(1))
                    growth_value = float(match.group(2)) if match.group(2) else None
                    
                    result = {"base": base_value}
                    if growth_value is not None:
                        result["growth"] = growth_value
                    
                    return result
                    
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Failed to parse numeric values for {stat_name}: {e}")
                    continue
        
        return None

    def _normalize_stat_name(self, name: str) -> str:
        """
        Normalize stat names to standard format.
        
        Args:
            name: Raw stat name from wiki
            
        Returns:
            Normalized stat name
        """
        name_lower = name.lower().strip()
        
        # Normalization mapping
        normalizations = {
            'health': 'hp',
            'health points': 'hp',
            'mana': 'mp', 
            'mana points': 'mp',
            'attack damage': 'ad',
            'attack dmg': 'ad',
            'damage': 'ad',
            'armour': 'armor',
            'ar': 'armor',
            'magic resistance': 'mr',
            'magic resist': 'mr', 
            'magic res': 'mr',
            'attack speed': 'attack_speed',
            'attackspeed': 'attack_speed',
            'as': 'attack_speed',
            'movement speed': 'movement_speed',
            'movespeed': 'movement_speed',
            'move speed': 'movement_speed',
            'ms': 'movement_speed',
            'attack range': 'range',
            'atk range': 'range'
        }
        
        return normalizations.get(name_lower, name_lower)

    def _validate_stat_data(self, stats: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
        """
        Validate parsed stat data and log warnings for outliers.
        
        Args:
            stats: Dictionary of parsed champion stats
            
        Returns:
            Validated stats dictionary (same as input, with logging)
        """
        # Define expected ranges for champion stats
        stat_ranges = {
            'hp': {'min_base': 300, 'max_base': 800, 'min_growth': 50, 'max_growth': 150},
            'mp': {'min_base': 0, 'max_base': 500, 'min_growth': 0, 'max_growth': 100},
            'ad': {'min_base': 40, 'max_base': 80, 'min_growth': 2, 'max_growth': 6},
            'armor': {'min_base': 20, 'max_base': 60, 'min_growth': 2, 'max_growth': 8},
            'mr': {'min_base': 25, 'max_base': 45, 'min_growth': 0, 'max_growth': 3},
            'attack_speed': {'min_base': 0.5, 'max_base': 1.0, 'min_growth': 1, 'max_growth': 5},
            'movement_speed': {'min_base': 300, 'max_base': 400},  # No growth typically
            'range': {'min_base': 125, 'max_base': 650}  # No growth typically
        }
        
        for stat_name, stat_data in stats.items():
            if stat_name in stat_ranges:
                ranges = stat_ranges[stat_name]
                
                # Check base value
                if 'base' in stat_data and isinstance(ranges, dict) and 'min_base' in ranges and 'max_base' in ranges:
                    base_val = stat_data['base']
                    if base_val < ranges['min_base'] or base_val > ranges['max_base']:
                        self.logger.warning(
                            f"{stat_name} base value {base_val} outside expected range "
                            f"[{ranges['min_base']}-{ranges['max_base']}]"
                        )
                
                # Check growth value (if applicable)
                if 'growth' in stat_data and isinstance(ranges, dict) and 'min_growth' in ranges and 'max_growth' in ranges:
                    growth_val = stat_data['growth']
                    if growth_val < ranges['min_growth'] or growth_val > ranges['max_growth']:
                        self.logger.warning(
                            f"{stat_name} growth value {growth_val} outside expected range "
                            f"[{ranges['min_growth']}-{ranges['max_growth']}]"
                        )
        
        return stats

    def parse_champion_abilities(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Parse champion abilities from the abilities section of a champion page.
        
        Extracts detailed ability information for Passive, Q, W, E, R abilities including:
        - Ability names and descriptions
        - Cooldowns, mana costs, and ranges
        - Damage values and scaling information
        - Special effects and mechanics
        
        Args:
            soup: BeautifulSoup object of the champion page
            
        Returns:
            Dictionary containing structured ability data:
            {
                "passive": {
                    "name": "Ability Name",
                    "description": "What the ability does...",
                    "cooldown": None,  # Passives typically don't have cooldowns
                    "cost": None,
                    "range": None,
                    "damage": "25-199 (+0.15 Bonus AD)",
                    "effects": ["Effect 1", "Effect 2"]
                },
                "Q": {
                    "name": "Q Ability Name",
                    "description": "Q ability description...",
                    "cooldown": "14/13/12/11/10",
                    "cost": "60/70/80/90/100",
                    "range": "750",
                    "damage": "80/120/160/200/240 (+0.4 AP)",
                    "effects": ["Channel ability", "Heals allies"]
                },
                # ... W, E, R similar structure
            }
            
        Raises:
            WikiScraperError: If abilities section cannot be found or parsed
        """
        self.logger.info("Parsing champion abilities")
        
        # Find the abilities section using existing method
        abilities_section = self._find_abilities_section(soup)
        if not abilities_section:
            raise WikiScraperError("Could not find abilities section for parsing")
        
        # Initialize abilities dictionary
        abilities = {}
        
        # Define ability types to look for
        ability_types = ['passive', 'Q', 'W', 'E', 'R']
        
        # Parse each ability type
        for ability_type in ability_types:
            ability_data = self._extract_single_ability(abilities_section, ability_type)
            if ability_data:
                abilities[ability_type] = ability_data
                self.logger.debug(f"Parsed {ability_type}: {ability_data.get('name', 'Unknown')}")
            else:
                self.logger.warning(f"Could not parse {ability_type} ability")
        
        # Validate the parsed abilities data
        validated_abilities = self._validate_ability_data(abilities)
        
        self.logger.info(f"Successfully parsed {len(validated_abilities)} abilities")
        return validated_abilities

    def _extract_single_ability(self, abilities_section: Tag, ability_type: str) -> Optional[Dict[str, Any]]:
        """
        Extract data for a single ability from the abilities section.
        
        Args:
            abilities_section: BeautifulSoup element containing abilities
            ability_type: Type of ability ('passive', 'Q', 'W', 'E', 'R')
            
        Returns:
            Dictionary with ability data or None if not found
        """
        self.logger.debug(f"Extracting {ability_type} ability data")
        
        # Initialize ability data structure
        ability_data: Dict[str, Any] = {
            "name": None,
            "description": None,
            "cooldown": None,
            "cost": None,
            "range": None,
            "damage": None,
            "healing": None,
            "effects": []
        }
        
        # Strategy 1: Look for headings with ability type
        heading_patterns = {
            'passive': ['passive', 'innate'],
            'Q': ['q ', 'q-', 'q:', 'ability q', 'first ability'],
            'W': ['w ', 'w-', 'w:', 'ability w', 'second ability'],
            'E': ['e ', 'e-', 'e:', 'ability e', 'third ability'],
            'R': ['r ', 'r-', 'r:', 'ability r', 'ultimate', 'ult']
        }
        
        ability_element = None
        patterns = heading_patterns.get(ability_type.lower(), [ability_type.lower()])
        
        # Look for headings containing ability patterns
        headings = abilities_section.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        for heading in headings:
            if isinstance(heading, Tag):
                heading_text = heading.get_text().lower().strip()
                for pattern in patterns:
                    if pattern in heading_text:
                        # Found heading, get content after it
                        content_elements = []
                        current = heading.next_sibling
                        
                        while current:
                            if isinstance(current, Tag):
                                if current.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                                    break  # Stop at next heading
                                content_elements.append(current)
                            current = current.next_sibling
                        
                        if content_elements:
                            ability_element = content_elements
                            break
                
                if ability_element:
                    break
        
        # Strategy 2: Look for ability cards/boxes with class patterns
        if not ability_element:
            def ability_class_filter(class_list: Any) -> bool:
                if not class_list:
                    return False
                class_string = ' '.join(class_list).lower()
                return any(term in class_string for term in ['ability', 'skill', ability_type.lower()])
            
            ability_cards = abilities_section.find_all('div', class_=ability_class_filter)
            
            for card in ability_cards:
                if isinstance(card, Tag):
                    card_text = card.get_text().lower()
                    for pattern in patterns:
                        if pattern in card_text:
                            ability_element = [card]
                            break
                    if ability_element:
                        break
        
        # Strategy 3: Content-based search within entire abilities section
        if not ability_element:
            # Look for any element containing the ability type and ability-like content
            all_elements = abilities_section.find_all(['div', 'p', 'span', 'table'])
            for element in all_elements:
                if isinstance(element, Tag):
                    element_text = element.get_text().lower()
                    for pattern in patterns:
                        if pattern in element_text and ('cooldown' in element_text or 'damage' in element_text or 'mana' in element_text):
                            ability_element = [element]
                            break
                    if ability_element:
                        break
        
        if not ability_element:
            self.logger.warning(f"Could not find {ability_type} ability element")
            return None
        
        # Extract data from found elements
        combined_text = ""
        for element in ability_element:
            if isinstance(element, Tag):
                combined_text += element.get_text() + " "
        
        self.logger.debug(f"{ability_type} ability text: {combined_text[:200]}...")
        
        # Extract ability name (usually first substantial text or in heading)
        ability_data["name"] = self._extract_ability_name(ability_element, ability_type)
        
        # Extract description
        ability_data["description"] = self._clean_ability_description(combined_text)
        
        # Parse numerical values
        values = self._parse_ability_values(combined_text)
        ability_data.update(values)
        
        # Extract effects list
        ability_data["effects"] = self._extract_ability_effects(combined_text)
        
        return ability_data

    def _extract_ability_name(self, ability_elements: list, ability_type: str) -> Optional[str]:
        """Extract the ability name from ability elements."""
        # Look for bold text, headings, or structured name patterns
        for element in ability_elements:
            if isinstance(element, Tag):
                # Check for bold/strong tags
                bold_elements = element.find_all(['b', 'strong'])
                for bold in bold_elements:
                    if isinstance(bold, Tag):
                        name = bold.get_text().strip()
                        if len(name) > 3 and not name.lower().startswith(ability_type.lower()):
                            return name
                
                # Check for heading text
                if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    name = element.get_text().strip()
                    # Remove ability type prefix if present
                    for prefix in [f"{ability_type}:", f"{ability_type} -", f"{ability_type}:"]:
                        if name.lower().startswith(prefix.lower()):
                            name = name[len(prefix):].strip()
                    if len(name) > 3:
                        return name
        
        return None

    def _clean_ability_description(self, text: str) -> Optional[str]:
        """Clean and extract the main description from ability text."""
        # Remove common prefixes and suffixes
        text = re.sub(r'^(passive|q|w|e|r)[\s\-:]+', '', text, flags=re.IGNORECASE)
        
        # Take the first substantial sentence/paragraph as description
        sentences = text.split('.')
        description = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20 and not re.search(r'\d+/\d+', sentence):  # Avoid stat lines
                description = sentence + "."
                break
        
        if not description and len(text) > 50:
            # Fallback: take first 200 characters
            description = text[:200].strip() + "..."
        
        return description.strip() if description else None

    def _parse_ability_values(self, text: str) -> Dict[str, Optional[str]]:
        """Parse cooldown, cost, range, and damage values from ability text."""
        values: Dict[str, Optional[str]] = {
            "cooldown": None,
            "cost": None,
            "range": None,
            "damage": None,
            "healing": None
        }
        
        # Cooldown patterns: "Cooldown: 14/13/12/11/10" or "CD: 8/7/6"
        cooldown_match = re.search(r'cooldown[:\s]+(\d+(?:/\d+)*)', text, re.IGNORECASE)
        if cooldown_match:
            values["cooldown"] = cooldown_match.group(1)
        
        # Cost patterns: "Mana Cost: 60/70/80" or "Cost: 50 mana"
        cost_match = re.search(r'(?:mana\s+)?cost[:\s]+(\d+(?:/\d+)*)', text, re.IGNORECASE)
        if cost_match:
            values["cost"] = cost_match.group(1)
        
        # Range patterns: "Range: 750" or "Cast Range: 600"
        range_match = re.search(r'(?:cast\s+)?range[:\s]+(\d+)', text, re.IGNORECASE)
        if range_match:
            values["range"] = range_match.group(1)
        
        # Damage patterns: "80/120/160/200/240 (+0.4 AP)" or "Damage: 100-300"
        damage_match = re.search(r'damage[:\s]*(\d+(?:[/-]\d+)*(?:\s*\([^)]+\))?)', text, re.IGNORECASE)
        if damage_match:
            values["damage"] = damage_match.group(1)
        
        # Healing patterns: similar to damage but for heals
        healing_match = re.search(r'heal(?:ing)?[:\s]*(\d+(?:[/-]\d+)*(?:\s*\([^)]+\))?)', text, re.IGNORECASE)
        if healing_match:
            values["healing"] = healing_match.group(1)
        
        return values

    def _extract_ability_effects(self, text: str) -> List[str]:
        """Extract list of ability effects from description text."""
        effects: List[str] = []
        
        # Look for common effect keywords
        effect_patterns = [
            r'channel(?:ing|s)?',
            r'stun(?:s)?',
            r'slow(?:s)?',
            r'heal(?:s|ing)?',
            r'shield(?:s)?',
            r'dash(?:es)?',
            r'teleport(?:s)?',
            r'stealth',
            r'invisib(?:le|ility)',
            r'knockup',
            r'knockback',
            r'silence(?:s)?',
            r'root(?:s)?',
            r'reduce(?:s)?\s+cooldown',
            r'increase(?:s)?\s+(?:attack\s+speed|movement\s+speed|damage)',
        ]
        
        for pattern in effect_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                # Extract the context around the effect
                match = re.search(f'.{{0,20}}{pattern}.{{0,30}}', text, re.IGNORECASE)
                if match:
                    effect_text = match.group(0).strip()
                    if effect_text not in effects:
                        effects.append(effect_text)
        
        return effects[:5]  # Limit to 5 most relevant effects

    def _validate_ability_data(self, abilities: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Validate and clean up parsed ability data."""
        validated = {}
        
        for ability_type, ability_data in abilities.items():
            if ability_data and isinstance(ability_data, dict):
                # Ensure all required fields exist
                validated_ability = {
                    "name": ability_data.get("name"),
                    "description": ability_data.get("description"),
                    "cooldown": ability_data.get("cooldown"),
                    "cost": ability_data.get("cost"),
                    "range": ability_data.get("range"),
                    "damage": ability_data.get("damage"),
                    "healing": ability_data.get("healing"),
                    "effects": ability_data.get("effects", [])
                }
                
                # Validate that we have at least a name or description
                if validated_ability["name"] or validated_ability["description"]:
                    validated[ability_type] = validated_ability
                    self.logger.debug(f"Validated {ability_type}: {validated_ability['name']}")
                else:
                    self.logger.warning(f"Skipping {ability_type}: insufficient data")
        
        return validated

    def _validate_page_structure(self, soup: BeautifulSoup) -> Dict[str, bool]:
        """
        Validate that expected sections exist and contain meaningful data.
        
        Args:
            soup: BeautifulSoup object of the champion page
            
        Returns:
            Dictionary mapping section names to validation results
        """
        self.logger.debug("Validating page structure")
        
        sections = self.find_champion_data_sections(soup)
        validation = {}
        
        # Validate stats section
        stats = sections.get('stats')
        if stats:
            stats_text = stats.get_text().lower()
            has_hp = 'hp' in stats_text or 'health' in stats_text
            has_stats = any(stat in stats_text for stat in ['ad', 'armor', 'attack', 'damage'])
            validation['stats'] = has_hp and has_stats
        else:
            validation['stats'] = False
        
        # Validate abilities section
        abilities = sections.get('abilities')
        if abilities:
            abilities_text = abilities.get_text().lower()
            has_abilities = any(ability in abilities_text for ability in ['passive', 'ability'])
            validation['abilities'] = has_abilities
        else:
            validation['abilities'] = False
        
        # Validate overview section
        overview = sections.get('overview')
        if overview:
            overview_text = overview.get_text().strip()
            validation['overview'] = len(overview_text) > 50
        else:
            validation['overview'] = False
        
        self.logger.debug(f"Page structure validation: {validation}")
        return validation

    def parse_champion_stats_safe(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Enhanced stats parsing with graceful degradation"""
        try:
            result = self.parse_champion_stats(soup)
            self.metrics.parsing_successes += 1
            self.logger.debug("Stats parsing successful")
            return result
        except Exception as e:
            self.logger.warning(f"Stats parsing failed: {e}")
            self.metrics.parsing_failures += 1
            error_entry = f"{datetime.now().isoformat()}: Stats parsing failed: {e}"
            self.metrics.errors.append(error_entry)
            return {
                "error": "Failed to parse stats",
                "partial_data": True,
                "stats": {},
                "error_details": str(e)
            }
            
    def parse_champion_abilities_safe(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Enhanced abilities parsing with graceful degradation"""  
        try:
            result = self.parse_champion_abilities(soup)
            self.metrics.parsing_successes += 1
            self.logger.debug("Abilities parsing successful")
            return result
        except Exception as e:
            self.logger.warning(f"Abilities parsing failed: {e}")
            self.metrics.parsing_failures += 1
            error_entry = f"{datetime.now().isoformat()}: Abilities parsing failed: {e}"
            self.metrics.errors.append(error_entry)
            return {
                "error": "Failed to parse abilities", 
                "partial_data": True,
                "abilities": {},
                "error_details": str(e)
            }
            
    def get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        return asdict(self.metrics)
        
    def reset_metrics(self) -> None:
        """Reset performance metrics"""
        self.metrics = ScrapingMetrics()
        self.logger.info("Performance metrics reset")
        
    async def cleanup_cache(self) -> int:
        """Clean up expired cache entries"""
        if self.cache_manager:
            removed_count = self.cache_manager.cleanup_expired()
            self.logger.info(f"Cache cleanup completed: {removed_count} entries removed")
            return removed_count
        return 0
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information and statistics"""
        if not self.cache_manager:
            return {"cache_enabled": False}
            
        cache_info = {
            "cache_enabled": True,
            "cache_dir": str(self.cache_manager.cache_dir),
            "ttl_hours": self.cache_manager.ttl.total_seconds() / 3600,
            "cache_hits": self.metrics.cache_hits,
            "cache_misses": self.metrics.cache_misses,
            "hit_rate": 0.0
        }
        
        total_requests = self.metrics.cache_hits + self.metrics.cache_misses
        if total_requests > 0:
            cache_info["hit_rate"] = self.metrics.cache_hits / total_requests
            
        # Add metadata info if available
        try:
            metadata = self.cache_manager._load_metadata()
            cache_info["cached_entries"] = len(metadata)
        except Exception:
            cache_info["cached_entries"] = 0
            
        return cache_info


# Example usage and testing functions
async def test_wiki_scraper() -> None:
    """Test function to verify WikiScraper functionality"""
    async with WikiScraper() as scraper:
        # Test connection
        if not await scraper.test_connection():
            print("❌ Connection test failed")
            return
        
        print("✅ Connection test successful")
        
        # Test fetching Taric's page
        try:
            soup = await scraper.fetch_champion_page("Taric")
            title_elem = soup.find('title')
            title = title_elem.get_text() if title_elem is not None else "No title"
            print(f"✅ Successfully fetched Taric's page: {title}")
        except Exception as e:
            print(f"❌ Failed to fetch Taric's page: {e}")


if __name__ == "__main__":
    # Configure logging for testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run test
    asyncio.run(test_wiki_scraper()) 
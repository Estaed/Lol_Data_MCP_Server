"""
Base Scraper for League of Legends Wiki

This module provides the core infrastructure for scraping the LoL Wiki,
including a base class with shared functionality for HTTP requests,
caching, rate limiting, and basic page fetching.
"""

import asyncio
import json
import hashlib
import logging
import os
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
try:
    from src.models.exceptions import ChampionNotFoundError
except ImportError:
    # Fallback for different import contexts
    try:
        from models.exceptions import ChampionNotFoundError
    except ImportError:
        # Define locally if import fails
        class ChampionNotFoundError(Exception):
            def __init__(self, champion_name: str):
                self.champion_name = champion_name
                super().__init__(f"Champion '{champion_name}' not found")


class WikiScraperError(Exception):
    """Base exception for wiki scraper errors"""
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
        # self._ensure_cache_dir() # Defer directory creation until needed

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
        self._ensure_cache_dir()  # Ensure cache directory exists before writing
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


class BaseScraper:
    """Base class for LoL Wiki scrapers"""

    BASE_URL = "https://wiki.leagueoflegends.com/en-us/"  # Add trailing slash for urljoin
    CHAMPION_URL_TEMPLATE = "{champion_name}"  # Remove leading slash for relative path

    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        enable_cache: bool = True,
        cache_ttl_hours: int = 24
    ):
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.last_request_time = 0.0
        self.client: Optional[httpx.AsyncClient] = None
        self.enable_cache = enable_cache
        self.cache_manager = CacheManager(ttl_hours=cache_ttl_hours) if enable_cache else None
        self.metrics = ScrapingMetrics()
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self) -> 'BaseScraper':
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def _ensure_client(self) -> None:
        """Initialize httpx.AsyncClient if not already initialized"""
        if self.client is None or self.client.is_closed:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            }
            self.client = httpx.AsyncClient(
                http2=True,
                follow_redirects=True,
                timeout=self.timeout,
                headers=headers
            )
            self.logger.info("httpx.AsyncClient initialized.")

    async def close(self) -> None:
        """Close the httpx client"""
        if self.client and not self.client.is_closed:
            await self.client.aclose()
            self.logger.info("httpx.AsyncClient closed.")

    def _update_metrics(self, start_time: float, success: bool, cache_hit: bool = False, error: Optional[str] = None) -> None:
        """Update scraping performance metrics"""
        if cache_hit:
            self.metrics.cache_hits += 1
        else:
            self.metrics.cache_misses += 1
            request_time = time.monotonic() - start_time
            self.metrics.total_request_time += request_time
            self.metrics.total_requests += 1
            if self.metrics.total_requests > 0:
                self.metrics.avg_request_time = self.metrics.total_request_time / self.metrics.total_requests

        if success:
            self.metrics.parsing_successes += 1
        else:
            self.metrics.parsing_failures += 1
            if error:
                self.metrics.errors.append(error)

    async def _rate_limit(self) -> None:
        """Enforce a delay between requests"""
        elapsed = time.monotonic() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.monotonic()

    def _build_champion_url(self, champion_name: str) -> str:
        """Construct the full URL for a champion page"""
        normalized_name = self.normalize_champion_name(champion_name)
        path = self.CHAMPION_URL_TEMPLATE.format(champion_name=normalized_name)
        return urljoin(self.BASE_URL, path)

    async def _make_request(self, url: str) -> httpx.Response:
        """Make an HTTP GET request with retries"""
        await self._ensure_client()
        for attempt in range(self.max_retries):
            try:
                await self._rate_limit()
                self.logger.info(f"Fetching URL: {url} (Attempt {attempt + 1})")
                response = await self.client.get(url)
                response.raise_for_status()
                return response
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                self.logger.warning(
                    f"Request failed (Attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise WikiScraperError(f"Failed to fetch URL after {self.max_retries} attempts: {url}") from e
    
    def normalize_champion_name(self, name: str) -> str:
        """
        Normalize champion name for wiki lookup.
        Example: "Kai'Sa" -> "Kai%27Sa", "Wukong" -> "Wukong", "Nunu & Willump" -> "Nunu"
        """
        # Title case and strip whitespace
        normalized = name.strip().title()

        # General rule for names with '&'
        if " & " in normalized:
            normalized = normalized.split(" & ")[0]
            
        # Replace spaces with underscores for URL compatibility
        normalized = normalized.replace(' ', '_')

        # Handle apostrophes for URL compatibility
        normalized = normalized.replace("'", "%27")

        return normalized

    async def fetch_champion_page(self, champion_name: str) -> BeautifulSoup:
        """
        Fetch and parse a champion's wiki page, using cache if available.
        """
        start_time = time.monotonic()
        
        # Check cache first
        if self.enable_cache and self.cache_manager.is_cache_valid(champion_name):
            cached_content = self.cache_manager.get_cached_content(champion_name)
            if cached_content:
                self.logger.info(f"Cache hit for {champion_name}")
                self._update_metrics(start_time, success=True, cache_hit=True)
                return BeautifulSoup(cached_content, "lxml")
        
        self.logger.info(f"Cache miss for {champion_name}, fetching from web.")
        
        # Fetch from web
        url = self._build_champion_url(champion_name)
        try:
            response = await self._make_request(url)
            
            # Handle potential Brotli compression issue
            content = response.text
            
            # Check if content seems to be still compressed (binary data instead of text)
            if len(content) > 100 and not any(char in content for char in ['<', '>', 'html', 'div']):
                self.logger.warning("Content appears to be compressed, attempting manual decompression")
                import brotli
                try:
                    # Try Brotli decompression
                    decompressed = brotli.decompress(response.content)
                    content = decompressed.decode('utf-8')
                    self.logger.info("Successfully decompressed content manually")
                except Exception as e:
                    self.logger.error(f"Manual decompression failed: {e}")
                    # Fall back to original content
                    content = response.text
            
            # Cache the new content
            if self.enable_cache:
                self.cache_manager.cache_content(champion_name, content)
            
            self._update_metrics(start_time, success=True, cache_hit=False)
            return BeautifulSoup(content, "lxml")
            
        except WikiScraperError as e:
            self._update_metrics(start_time, success=False, cache_hit=False, error=str(e))
            raise ChampionNotFoundError(champion_name) from e

    def _create_selenium_driver(self) -> webdriver.Chrome:
        """Creates and configures a Selenium WebDriver."""
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        try:
            driver = webdriver.Chrome(options=options)
            return driver
        except Exception as e:
            self.logger.error(f"Failed to initialize Selenium WebDriver: {e}")
            raise WikiScraperError("Could not start Selenium WebDriver.") from e 
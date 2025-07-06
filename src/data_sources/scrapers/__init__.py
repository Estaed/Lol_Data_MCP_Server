"""
Data Sources Scrapers Package

This package contains web scrapers for various League of Legends data sources.

Available scrapers:
- BaseScraper: Provides base functionality for web scraping.
- StatsScraper: Scrapes League of Legends Wiki for champion stats.
"""

from .base_scraper import BaseScraper, CacheManager
from .stats_scraper import StatsScraper, WikiScraperError

__all__ = ["BaseScraper", "StatsScraper", "WikiScraperError", "CacheManager"] 
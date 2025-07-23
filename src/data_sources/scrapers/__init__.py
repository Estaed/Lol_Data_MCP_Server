"""
Data Sources Scrapers Package

This package contains web scrapers for various League of Legends data sources.

Available scrapers:
- BaseScraper: Provides base functionality for web scraping.
- Champion scrapers in champions/ subfolder
- Item scrapers in items/ subfolder
"""

from .base_scraper import BaseScraper, CacheManager

__all__ = ["BaseScraper", "CacheManager"] 
"""
Data Sources Scrapers Package

This package contains web scrapers for various League of Legends data sources.

Available scrapers:
- WikiScraper: Scrapes League of Legends Wiki for champion data
"""

from .wiki_scraper import WikiScraper

__all__ = ["WikiScraper"] 
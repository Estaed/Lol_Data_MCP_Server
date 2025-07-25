"""
Runes scrapers package for League of Legends Wiki

This package contains scrapers for extracting rune data and patch history
from the League of Legends Wiki, following the established patterns used
for champions and items.
"""

from .rune_data_scraper import RuneDataScraper
from .rune_patch_scraper import RunePatchScraper

__all__ = [
    'RuneDataScraper',
    'RunePatchScraper'
]
"""
This package contains Pydantic models for the application.

It is divided into sub-modules for better organization:
- `data_models`: Core data structures (e.g., ChampionData, ChampionStats).
- `input_models`: Schemas for tool inputs (e.g., GetChampionDataInput).
- `exceptions`: Custom exceptions related to data models.
"""

from .data_models import ChampionData, ChampionStats
from .input_models import GetChampionDataInput
from .exceptions import ChampionNotFoundError

__all__ = [
    "ChampionData",
    "ChampionStats",
    "GetChampionDataInput",
    "ChampionNotFoundError",
] 
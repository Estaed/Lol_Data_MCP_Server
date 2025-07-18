"""
Services package for League of Legends MCP Server

This package contains service layer implementations for handling data operations
and business logic for the LoL Data MCP Server.
"""

from .stats_service import StatsService

__all__ = ["StatsService"]
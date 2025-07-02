"""
Stat Calculator for League of Legends Champion Statistics

This module provides utilities for parsing and calculating champion stat formulas
from the LoL Wiki, including support for complex formulas with quadratic growth.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, List


@dataclass
class StatFormula:
    """
    Represents a champion stat formula that can calculate values for any level.
    
    Supports different growth types:
    - none: Constant value (e.g., "550")
    - linear: Linear growth (e.g., "645 + 99 × (level-1)")
    - quadratic: Quadratic growth (e.g., "605 + 88 × (level-1)²")
    """
    base_value: float
    growth_coefficient: float = 0.0
    growth_type: str = "none"  # "none", "linear", "quadratic"
    is_percentage: bool = False
    max_value: Optional[float] = None
    
    def calculate_at_level(self, level: int) -> float:
        """
        Calculate stat value at a specific champion level (1-18).
        
        Args:
            level: Champion level (1-18)
            
        Returns:
            Calculated stat value
            
        Raises:
            ValueError: If level is not between 1 and 18
        """
        if not 1 <= level <= 18:
            raise ValueError(f"Level must be between 1 and 18, got {level}")
            
        if self.growth_type == "none":
            return self.base_value
        elif self.growth_type == "linear":
            # Traditional per-level growth: base + (growth × (level - 1))
            result = self.base_value + (self.growth_coefficient * (level - 1))
        elif self.growth_type == "quadratic":
            # Level squared growth: base + (growth × (level - 1)²)
            result = self.base_value + (self.growth_coefficient * (level - 1) ** 2)
        else:
            result = self.base_value
        
        # Apply max value cap if specified
        if self.max_value is not None:
            result = min(result, self.max_value)
            
        return result
    
    def get_level_range(self, start_level: int = 1, end_level: int = 18) -> Dict[int, float]:
        """
        Get stat values for a range of levels.
        
        Args:
            start_level: Starting level (default: 1)
            end_level: Ending level (default: 18)
            
        Returns:
            Dictionary mapping level to calculated value
        """
        return {level: self.calculate_at_level(level) for level in range(start_level, end_level + 1)}
    
    def get_growth_at_level(self, level: int) -> float:
        """
        Get the growth contribution at a specific level.
        
        Args:
            level: Champion level (1-18)
            
        Returns:
            Growth contribution (total value - base value)
        """
        if level == 1:
            return 0.0
        return self.calculate_at_level(level) - self.base_value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert formula to dictionary for serialization"""
        return {
            "base_value": self.base_value,
            "growth_coefficient": self.growth_coefficient,
            "growth_type": self.growth_type,
            "is_percentage": self.is_percentage,
            "max_value": self.max_value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StatFormula":
        """Create formula from dictionary"""
        return cls(
            base_value=data["base_value"],
            growth_coefficient=data.get("growth_coefficient", 0.0),
            growth_type=data.get("growth_type", "none"),
            is_percentage=data.get("is_percentage", False),
            max_value=data.get("max_value")
        )


class StatFormulaParser:
    """Parses complex stat formulas from LoL Wiki text"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def parse_formula(self, text: str, stat_names: List[str]) -> Optional[StatFormula]:
        """
        Parse complex stat formulas from wiki text.
        
        Supports formats like:
        - "605 (+ 88 × M²)" - quadratic growth
        - "645 (+ 99 × M)" - linear growth  
        - "175%" - percentage values
        - "550" - simple values
        - "HP: 645 (+99)" - legacy format
        
        Args:
            text: Text to parse
            stat_names: List of possible stat names to look for
            
        Returns:
            StatFormula object if parsing successful, None otherwise
        """
        text_lower = text.lower()
        
        for stat_name in stat_names:
            formula = self._try_parse_patterns(text_lower, stat_name)
            if formula:
                self.logger.debug(f"Parsed {stat_name} formula: {formula}")
                return formula
        
        return None
    
    def _try_parse_patterns(self, text: str, stat_name: str) -> Optional[StatFormula]:
        """Try different regex patterns to parse formulas"""
        
        # Escape stat name for regex
        escaped_name = re.escape(stat_name.lower())
        
        # Pattern 1: Quadratic growth "605 (+ 88 × M²)" or variations
        patterns_quadratic = [
            rf'{escaped_name}\s*:?\s*([0-9]+\.?[0-9]*)\s*\(\+\s*([0-9]+\.?[0-9]*)\s*×\s*m²\)',
            rf'{escaped_name}\s*:?\s*([0-9]+\.?[0-9]*)\s*\(\+\s*([0-9]+\.?[0-9]*)\s*×\s*lvl²\)',
            rf'{escaped_name}\s*:?\s*([0-9]+\.?[0-9]*)\s*\(\+\s*([0-9]+\.?[0-9]*)\s*×\s*level²\)',
            rf'{escaped_name}\s*:?\s*([0-9]+\.?[0-9]*)\s*\(\+\s*([0-9]+\.?[0-9]*)\s*\*\s*m²\)',
        ]
        
        for pattern in patterns_quadratic:
            match = re.search(pattern, text)
            if match:
                try:
                    base = float(match.group(1))
                    growth = float(match.group(2))
                    return StatFormula(base_value=base, growth_coefficient=growth, growth_type="quadratic")
                except (ValueError, IndexError) as e:
                    self.logger.warning(f"Failed to parse quadratic formula: {e}")
                    continue
        
        # Pattern 2: Linear growth "605 (+ 88 × M)" or variations
        patterns_linear = [
            rf'{escaped_name}\s*:?\s*([0-9]+\.?[0-9]*)\s*\(\+\s*([0-9]+\.?[0-9]*)\s*×\s*m\)',
            rf'{escaped_name}\s*:?\s*([0-9]+\.?[0-9]*)\s*\(\+\s*([0-9]+\.?[0-9]*)\s*×\s*lvl\)',
            rf'{escaped_name}\s*:?\s*([0-9]+\.?[0-9]*)\s*\(\+\s*([0-9]+\.?[0-9]*)\s*×\s*level\)',
            rf'{escaped_name}\s*:?\s*([0-9]+\.?[0-9]*)\s*\(\+\s*([0-9]+\.?[0-9]*)\s*\*\s*m\)',
        ]
        
        for pattern in patterns_linear:
            match = re.search(pattern, text)
            if match:
                try:
                    base = float(match.group(1))
                    growth = float(match.group(2))
                    return StatFormula(base_value=base, growth_coefficient=growth, growth_type="linear")
                except (ValueError, IndexError) as e:
                    self.logger.warning(f"Failed to parse linear formula: {e}")
                    continue
        
        # Pattern 3: Percentage values "175%"
        pattern_percentage = rf'{escaped_name}\s*:?\s*([0-9]+\.?[0-9]*)%'
        match = re.search(pattern_percentage, text)
        if match:
            try:
                value = float(match.group(1))
                return StatFormula(base_value=value, is_percentage=True)
            except (ValueError, IndexError) as e:
                self.logger.warning(f"Failed to parse percentage: {e}")
        
        # Pattern 4: Legacy format "HP: 645 (+99)" - linear growth
        pattern_legacy = rf'{escaped_name}\s*:?\s*([0-9]+\.?[0-9]*)\s*\(\+\s*([0-9]+\.?[0-9]*)\s*(?:per\s+level)?\)'
        match = re.search(pattern_legacy, text)
        if match:
            try:
                base = float(match.group(1))
                growth = float(match.group(2))
                return StatFormula(base_value=base, growth_coefficient=growth, growth_type="linear")
            except (ValueError, IndexError) as e:
                self.logger.warning(f"Failed to parse legacy format: {e}")
        
        # Pattern 5: Simple values "550" (must not be followed by +, ×, %, etc.)
        pattern_simple = rf'{escaped_name}\s*:?\s*([0-9]+\.?[0-9]*)\s*(?![+×%*])'
        match = re.search(pattern_simple, text)
        if match:
            try:
                value = float(match.group(1))
                return StatFormula(base_value=value)
            except (ValueError, IndexError) as e:
                self.logger.warning(f"Failed to parse simple value: {e}")
        
        return None
    
    def parse_multiple_stats(self, text: str, stat_mapping: Dict[str, List[str]]) -> Dict[str, StatFormula]:
        """
        Parse multiple stats from text using a mapping of stat keys to possible names.
        
        Args:
            text: Text to parse
            stat_mapping: Dictionary mapping stat keys to lists of possible names
            
        Returns:
            Dictionary mapping stat keys to parsed formulas
        """
        results = {}
        
        for stat_key, stat_names in stat_mapping.items():
            formula = self.parse_formula(text, stat_names)
            if formula:
                results[stat_key] = formula
                self.logger.debug(f"Successfully parsed {stat_key}: {formula}")
        
        return results


class StatCalculator:
    """Utility class for stat calculations and conversions"""
    
    @staticmethod
    def calculate_stats_at_level(formulas: Dict[str, StatFormula], level: int) -> Dict[str, float]:
        """
        Calculate all stats at a specific level.
        
        Args:
            formulas: Dictionary of stat formulas
            level: Champion level (1-18)
            
        Returns:
            Dictionary of calculated stat values
        """
        return {stat_name: formula.calculate_at_level(level) 
                for stat_name, formula in formulas.items()}
    
    @staticmethod
    def get_stat_progression(formulas: Dict[str, StatFormula], 
                           start_level: int = 1, 
                           end_level: int = 18) -> Dict[str, Dict[int, float]]:
        """
        Get stat progression for multiple stats across level range.
        
        Args:
            formulas: Dictionary of stat formulas
            start_level: Starting level
            end_level: Ending level
            
        Returns:
            Nested dictionary: {stat_name: {level: value}}
        """
        return {stat_name: formula.get_level_range(start_level, end_level)
                for stat_name, formula in formulas.items()}
    
    @staticmethod
    def convert_legacy_format(legacy_stats: Dict[str, Dict[str, float]]) -> Dict[str, StatFormula]:
        """
        Convert legacy stat format to StatFormula objects.
        
        Args:
            legacy_stats: Legacy format with 'base' and 'growth' keys
            
        Returns:
            Dictionary of StatFormula objects
        """
        formulas = {}
        
        for stat_name, stat_data in legacy_stats.items():
            if isinstance(stat_data, dict):
                base = stat_data.get('base', 0.0)
                growth = stat_data.get('growth', 0.0)
                growth_quadratic = stat_data.get('growth_quadratic')
                is_percentage = stat_data.get('is_percentage', False)
                
                if growth_quadratic is not None:
                    # Quadratic growth
                    formulas[stat_name] = StatFormula(
                        base_value=base,
                        growth_coefficient=growth_quadratic,
                        growth_type="quadratic",
                        is_percentage=is_percentage
                    )
                elif growth > 0:
                    # Linear growth
                    formulas[stat_name] = StatFormula(
                        base_value=base,
                        growth_coefficient=growth,
                        growth_type="linear",
                        is_percentage=is_percentage
                    )
                else:
                    # No growth
                    formulas[stat_name] = StatFormula(
                        base_value=base,
                        is_percentage=is_percentage
                    )
            else:
                # Simple numeric value
                formulas[stat_name] = StatFormula(base_value=float(stat_data))
        
        return formulas

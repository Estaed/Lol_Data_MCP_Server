"""
Pydantic Models for Tool Inputs
"""

from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class GetChampionDataInput(BaseModel):
    """Input schema for get_champion_data tool"""

    champion: str = Field(..., description="Champion name")
    include: List[str] = Field(
        default=["stats"], description="Data sections to include"
    )
    level: Optional[int] = Field(None, ge=1, le=18, description="Specific level for stats (1-18). If not provided, returns base stats.")

    @field_validator("include")
    @classmethod
    def validate_include_options(cls, v: List[str]) -> List[str]:
        valid_options = {"stats"}
        invalid = set(v) - valid_options
        if invalid:
            raise ValueError(f"Invalid include options: {invalid}")
        return v 
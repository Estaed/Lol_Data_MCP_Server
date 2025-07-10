"""
Pydantic Models for Champion Data
"""

from typing import Optional
from pydantic import BaseModel, Field


class ChampionStats(BaseModel):
    """Champion comprehensive statistics model"""
    
    # Core stats
    health: Optional[float] = Field(None, description="Base health points")
    health_per_level: Optional[float] = Field(None, description="Health gained per level")
    mana: Optional[float] = Field(None, description="Base mana points")
    mana_per_level: Optional[float] = Field(None, description="Mana gained per level")
    attack_damage: Optional[float] = Field(None, description="Base attack damage")
    attack_damage_per_level: Optional[float] = Field(None, description="AD gained per level")
    armor: Optional[float] = Field(None, description="Base armor")
    armor_per_level: Optional[float] = Field(None, description="Armor gained per level")
    magic_resist: Optional[float] = Field(None, description="Base magic resistance")
    magic_resist_per_level: Optional[float] = Field(None, description="MR gained per level")
    movement_speed: Optional[float] = Field(None, description="Base movement speed")
    attack_range: Optional[float] = Field(None, description="Attack range")
    attack_speed: Optional[float] = Field(None, description="Base attack speed (attacks per second)")
    attack_speed_per_level: Optional[float] = Field(None, description="Attack speed gained per level")
    
    # Regeneration stats
    health_regen: Optional[float] = Field(None, description="Base health regeneration (HP5)")
    health_regen_per_level: Optional[float] = Field(None, description="HP5 gained per level")
    mana_regen: Optional[float] = Field(None, description="Base mana regeneration (MP5)")
    mana_regen_per_level: Optional[float] = Field(None, description="MP5 gained per level")
    
    # Critical and attack details
    critical_damage: Optional[float] = Field(None, description="Critical damage percentage")
    windup_percent: Optional[float] = Field(None, description="Attack windup percentage")
    attack_speed_ratio: Optional[float] = Field(None, description="Attack speed ratio")
    bonus_attack_speed: Optional[float] = Field(None, description="Bonus attack speed")
    base_attack_speed: Optional[float] = Field(None, description="Base attack speed (detailed)")
    
    # Missile and projectile
    missile_speed: Optional[float] = Field(None, description="Missile/projectile speed")
    
    # Unit radius data
    gameplay_radius: Optional[float] = Field(None, description="Gameplay radius for collision")
    selection_radius: Optional[float] = Field(None, description="Selection radius for clicking")
    pathing_radius: Optional[float] = Field(None, description="Pathing radius for movement")
    selection_height: Optional[float] = Field(None, description="Selection height for clicking")
    acquisition_radius: Optional[float] = Field(None, description="Acquisition radius for targeting")


class ChampionAbility(BaseModel):
    """Champion ability model with dynamic features"""
    
    name: str = Field(..., description="Ability name")
    description: Optional[str] = Field(None, description="Ability description")
    slot: Optional[str] = Field(None, description="Ability slot (Q, W, E, R, Passive)")
    
    # Dynamic ability stats - not all abilities have these
    cooldown: Optional[str] = Field(None, description="Ability cooldown (may be level-based)")
    cost: Optional[str] = Field(None, description="Ability cost (mana, energy, etc.)")
    range: Optional[str] = Field(None, description="Ability range")
    cast_time: Optional[str] = Field(None, description="Ability cast time")
    damage: Optional[str] = Field(None, description="Ability damage values")
    
    # Additional dynamic fields for future expansion
    channel_time: Optional[str] = Field(None, description="Channel time for channeled abilities")
    radius: Optional[str] = Field(None, description="Ability effect radius")
    duration: Optional[str] = Field(None, description="Effect duration")


class ChampionAbilities(BaseModel):
    """Champion abilities collection model"""
    
    passive: Optional[ChampionAbility] = Field(None, description="Passive ability")
    q: Optional[ChampionAbility] = Field(None, description="Q ability")
    w: Optional[ChampionAbility] = Field(None, description="W ability")
    e: Optional[ChampionAbility] = Field(None, description="E ability")
    r: Optional[ChampionAbility] = Field(None, description="R (Ultimate) ability")


class ChampionData(BaseModel):
    """Complete champion data model"""
    
    name: str = Field(..., description="Champion name")
    stats: Optional[ChampionStats] = Field(None, description="Champion statistics")
    abilities: Optional[ChampionAbilities] = Field(None, description="Champion abilities") 
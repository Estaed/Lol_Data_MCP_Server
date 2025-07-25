"""
Custom Exceptions for Models
"""


class ChampionNotFoundError(Exception):
    """Exception raised when a champion is not found"""
    
    def __init__(self, champion_name: str):
        self.champion_name = champion_name
        super().__init__(f"Champion '{champion_name}' not found")


class ItemNotFoundError(Exception):
    """Exception raised when an item is not found"""
    
    def __init__(self, item_name: str):
        self.item_name = item_name
        super().__init__(f"Item '{item_name}' not found")


class RuneNotFoundError(Exception):
    """Exception raised when a rune is not found"""
    
    def __init__(self, rune_name: str):
        self.rune_name = rune_name
        super().__init__(f"Rune '{rune_name}' not found") 
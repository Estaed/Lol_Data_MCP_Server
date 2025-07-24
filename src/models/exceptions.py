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
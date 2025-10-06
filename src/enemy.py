from src.character import Character

class Enemy(Character):
    """Represents an enemy character."""
    def __init__(self, name, stats, abilities, loot_table, ai_scripts, category="Normal", tags=None):
        super().__init__(name, stats)
        self.abilities = abilities
        self.loot_table = loot_table
        self.ai_scripts = ai_scripts
        self.category = category # e.g., "Normal", "Elite", "Boss"
        self.tags = tags if tags else []

        self.ai_state = {
            "current_script": None,
            "script_line": 0,
            "locked": False
        }
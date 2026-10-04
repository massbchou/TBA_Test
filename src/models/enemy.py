from dataclasses import dataclass, field
from src.models.character import Character


@dataclass
class Enemy(Character):
    """An enemy character constructed from data definitions."""
    enemy_id: str = ""
    category: str = "Normal"  # Normal | Elite | Boss | Special
    level: int = 1
    abilities: list[dict] = field(default_factory=list)
    loot_table: list[dict] = field(default_factory=list)
    attack_scripts: list[dict] = field(default_factory=list)
    ai_state: dict = field(default_factory=lambda: {
        "current_script": None,
        "script_line": 0,
        "locked": False,
    })

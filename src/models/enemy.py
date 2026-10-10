from dataclasses import dataclass, field
from typing import Any

from src.models.character import Character


@dataclass
class AIState:
    """Attack Script execution state for one enemy."""
    current_script: int | None = None
    line: int = 0
    locked: bool = False


@dataclass
class Enemy(Character):
    """An enemy character constructed from data definitions."""
    enemy_id: str = ""
    category: str = "Normal"  # Normal | Elite | Boss | Special
    level: int = 1
    intro: str = ""
    stolen_gold: int = 0
    abilities: list[dict[str, Any]] = field(default_factory=list)
    loot_table: list[dict[str, Any]] = field(default_factory=list)
    attack_scripts: list[dict[str, Any]] = field(default_factory=list)
    ai_state: AIState = field(default_factory=AIState)
    parsed_scripts: list[Any] | None = field(default=None, repr=False, compare=False)

    @staticmethod
    def _entry_id(entry: dict[str, Any]) -> str:
        return entry.get("ability_id") or entry.get("spell_id") or ""

    def ability_ids(self) -> list[str]:
        """Ids of every ability or spell this enemy can use."""
        return [aid for aid in (self._entry_id(e) for e in self.abilities) if aid]

    def owns(self, action_id: str) -> bool:
        return action_id in self.ability_ids()

    def ability_entry(self, action_id: str) -> dict[str, Any] | None:
        for entry in self.abilities:
            if self._entry_id(entry) == action_id:
                return entry
        return None

    def ready_abilities(self) -> list[str]:
        return [aid for aid in self.ability_ids() if self.is_ready(aid)]

    def trigger_cooldowns(self, action_id: str) -> None:
        """Applies an ability's cooldown map after use.

        ``"self": N`` puts the used ability on an N-turn cooldown; any other key
        ``"x": M`` raises ability x's cooldown to at least M (shared cooldowns).
        """
        entry = self.ability_entry(action_id)
        if entry is None:
            return
        for key, turns in entry.get("cooldowns", {}).items():
            if key == "self":
                self.set_cooldown(action_id, turns)
            else:
                self.set_cooldown(key, max(self.cooldowns.get(key, 0), turns))

"""Enemy AI Controller.

Evaluates an enemy's Attack Scripts and selects actions during combat.

EXTENSION POINT (Goal 3):
Implement the full scripting interpreter described in docs/AttackScriptDesignDocument.md
(activation conditions, interruptible locking, weighted choices, and combat state selectors).
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.models.enemy import Enemy
    from src.systems.combat import Combat


class AIController:
    """Manages AI decision-making for enemy combatants."""

    def __init__(self, data_loader: Any = None):
        self.data_loader = data_loader

    def decide_action(self, enemy: Enemy, combat_context: Combat) -> dict[str, Any] | None:
        """
        Determines the enemy's next combat action.

        Returns:
            A resolved action dictionary with ability details, or None if no action.
        """
        # Baseline fallback until full script parser is built in Goal 3:
        # Check enemy.abilities (list of {ability_id: ..., cooldowns: ...} or {spell_id: ...})
        if not enemy.abilities:
            # Fallback to a basic attack
            return {
                "name": "Basic Attack",
                "action_string": "DAMAGE 1_ENEMY CHOICE 1.0*STR PHYSICAL",
            }

        chosen_entry = random.choice(enemy.abilities)
        ability_id = chosen_entry.get("ability_id") or chosen_entry.get("spell_id")

        if self.data_loader and ability_id:
            if ability_id in self.data_loader.abilities:
                return self.data_loader.abilities[ability_id]
            if ability_id in self.data_loader.spells:
                return self.data_loader.spells[ability_id]

        return {
            "name": str(ability_id or "Strike"),
            "action_string": "DAMAGE 1_ENEMY CHOICE 1.0*STR PHYSICAL",
        }

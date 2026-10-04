"""Action System Orchestrator.

Parses and executes ability and spell actions defined by Action Strings or Predefined Actions.

EXTENSION POINT (Goal 3):
Implement the Lexer -> Parser -> Target Resolver -> Command Executor pipeline
specified in docs/ActionSystem.md.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.formula import evaluate_formula
from src.utils import roll_dice

if TYPE_CHECKING:
    from src.models.character import Character
    from src.systems.combat import Combat


class ActionOrchestrator:
    """Executes ability/spell effects via Action Strings or Predefined Actions."""

    def __init__(self, data_loader: Any = None):
        self.data_loader = data_loader

    def execute(
        self,
        caster: Character,
        action_data: dict[str, Any],
        targets: list[Character],
        combat_context: Combat | None = None,
    ) -> dict[str, Any]:
        """
        Executes an action from an ability/spell dictionary.

        Args:
            caster: Character executing the action.
            action_data: Ability or spell data dict (with action_string or predefined_action).
            targets: Resolved target character(s).
            combat_context: Active Combat instance for state/turn queries.

        Returns:
            Summary dict with execution results (e.g., {"damage_dealt": ..., "targets": ...}).
        """
        action_string = action_data.get("action_string", "")
        action_name = action_data.get("name", "Unknown Action")

        # Baseline execution until full Action DSL parser is implemented in Goal 3
        results: dict[str, Any] = {
            "action_name": action_name,
            "caster": caster.name,
            "effects": [],
        }

        if not targets:
            return results

        # Simple baseline parser for basic DAMAGE and HEAL lines
        if "HEAL" in action_string:
            heal_amount = int(caster.get_stat("int") + 10)
            for target in targets:
                healed = target.heal(heal_amount)
                results["effects"].append({"target": target.name, "type": "heal", "amount": healed})
        else:
            # Baseline offensive damage based on caster's strength or int
            stat_used = "int" if "int" in action_string.lower() else "str"
            base_power = float(caster.get_stat(stat_used))
            raw_damage = max(1, int(base_power * 1.2))

            for target in targets:
                dealt = target.take_damage(raw_damage)
                results["effects"].append({"target": target.name, "type": "damage", "amount": dealt})

        return results

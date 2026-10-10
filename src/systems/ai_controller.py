"""Enemy AI Controller.

Selects and runs an enemy's Attack Scripts (docs/ai_scripts.md):

1. If the active script is non-interruptible and its loop is unfinished, keep it.
2. Otherwise the first script whose activation_condition holds becomes active
   (falling back to the first script); switching scripts restarts at line 0.
3. One usable line runs per turn. Blank lines, CHANCE misses and lines whose
   ability is on cooldown are skipped without consuming the turn.
4. If a full pass finds nothing usable, use a random ready ability; if none is
   ready, the enemy waits.

Enemies with no scripts use a random ready ability. Enemies with no abilities at
all fall back to the basic Attack.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from src.systems.actions.context import ActionResult, ExecutionContext
from src.systems.actions.definitions import ActionDef, ActionRegistry
from src.systems.actions.nodes import Program
from src.systems.ai.script_parser import Script, evaluate, parse_scripts

if TYPE_CHECKING:
    from src.models.enemy import Enemy
    from src.systems.battle import Battle

logger = logging.getLogger("textrogue.ai")


class AIController:
    """Manages AI decision-making for enemy combatants."""

    def __init__(self, data_loader: Any = None, actions: ActionRegistry | None = None):
        self.data_loader = data_loader
        if actions is None:
            actions = getattr(data_loader, "actions", None) or ActionRegistry.build()
        self.actions = actions

    def scripts_for(self, enemy: "Enemy") -> list[Script]:
        """Parses (once) and caches the enemy's attack scripts on the enemy."""
        if enemy.parsed_scripts is None:
            scripts, diagnostics = parse_scripts(enemy.attack_scripts, source=f"enemy:{enemy.enemy_id or enemy.name}")
            for diag in diagnostics:
                logger.warning("%s", diag)
            enemy.parsed_scripts = scripts
        return enemy.parsed_scripts

    def _usable(self, enemy: "Enemy", ability_id: str | None) -> ActionDef | None:
        if not ability_id or not enemy.owns(ability_id) or not enemy.is_ready(ability_id):
            return None
        return self.actions.get(ability_id)

    def _random_ready(self, enemy: "Enemy", battle: "Battle") -> ActionDef | None:
        ready = [a for a in enemy.ready_abilities() if a in self.actions]
        return self.actions[battle.rng.choice(ready)] if ready else None

    def decide_action(self, enemy: "Enemy", battle: "Battle") -> ActionDef | None:
        """Returns the action to use this turn, or None to wait."""
        if not enemy.abilities:
            return self.actions.get("attack")
        scripts = self.scripts_for(enemy)
        if not scripts:
            return self._random_ready(enemy, battle)

        ctx = ExecutionContext(enemy, battle, None, Program(), ActionResult("", enemy.name))
        state = enemy.ai_state
        if not (state.locked and state.current_script is not None):
            chosen = next((i for i, s in enumerate(scripts) if s.is_active(ctx)), 0)
            if chosen != state.current_script:
                state.current_script = chosen
                state.line = 0
            state.locked = not scripts[chosen].interruptible

        script = scripts[state.current_script]
        for _ in range(len(script.lines)):
            stmt = script.lines[state.line]
            state.line = (state.line + 1) % len(script.lines)
            if state.line == 0:
                state.locked = False  # a full loop has completed
            action = self._usable(enemy, evaluate(stmt, ctx, battle.rng))
            if action is not None:
                return action
        return self._random_ready(enemy, battle)

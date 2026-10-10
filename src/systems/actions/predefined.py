"""Predefined Actions: hard-coded Python behaviours referenced from data with
``"predefined_action": {"name": ..., "params": {...}}``.

The player's Attack, Defend and Run are built-in predefined actions.
Register new ones with ``@register_predefined``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from src.systems.actions.context import ActionResult

if TYPE_CHECKING:
    from src.models.character import Character
    from src.systems.action_orchestrator import ActionOrchestrator
    from src.systems.actions.definitions import ActionDef
    from src.systems.battle import Battle

Predefined = Callable[["ActionOrchestrator", "Character", "ActionDef", "Battle", dict], ActionResult]
PREDEFINED: dict[str, Predefined] = {}

BUILTIN_ACTIONS: dict[str, dict[str, Any]] = {
    "attack": {
        "name": "Attack",
        "description": "A basic weapon strike.",
        "tags": ["physical", "offensive"],
        "predefined_action": {"name": "attack"},
    },
    "defend": {
        "name": "Defend",
        "description": "Brace yourself, raising Defense until the end of your next turn.",
        "tags": ["defensive"],
        "predefined_action": {"name": "defend"},
    },
    "run": {
        "name": "Run",
        "description": "Attempt to flee the battle.",
        "tags": ["escape"],
        "predefined_action": {"name": "run"},
    },
}

DEFAULT_DEFEND_FORMULA = "5+CON/2"
DEFAULT_RUN = {"base_chance": 50, "speed_factor": 0.5, "min_chance": 10, "max_chance": 90}


def register_predefined(name: str) -> Callable[[Predefined], Predefined]:
    def decorator(fn: Predefined) -> Predefined:
        PREDEFINED[name] = fn
        return fn
    return decorator


@register_predefined("attack")
def attack(orchestrator, caster, action_def, battle, params) -> ActionResult:
    formula = params.get("formula") or getattr(caster, "basic_attack", None) or "1.0*STR"
    return orchestrator.execute_string(caster, f"DAMAGE 1_ENEMY CHOICE {formula} PHYSICAL", battle, action=action_def)


@register_predefined("defend")
def defend(orchestrator, caster, action_def, battle, params) -> ActionResult:
    formula = params.get("formula") or battle.settings.get("combat", {}).get("defend_formula", DEFAULT_DEFEND_FORMULA)
    return orchestrator.execute_string(caster, f"BUFF SELF DEFENSE {formula} 1_TURN", battle, action=action_def)


def run_chance(caster: "Character", battle: "Battle") -> float:
    cfg = {**DEFAULT_RUN, **battle.settings.get("combat", {}).get("run", {})}
    foes = battle.enemies_of(caster)
    avg_speed = sum(f.get_stat("speed") for f in foes) / len(foes) if foes else 0
    chance = cfg["base_chance"] + (caster.get_stat("speed") - avg_speed) * cfg["speed_factor"]
    return max(cfg["min_chance"], min(cfg["max_chance"], chance))


@register_predefined("run")
def run(orchestrator, caster, action_def, battle, params) -> ActionResult:
    result = ActionResult(action_def.id, caster.name)
    if not battle.allow_run:
        battle.narrate("  There is no escape from this fight!")
        return result
    chance = run_chance(caster, battle)
    if battle.rng.uniform(0, 100) < chance:
        battle.fled = True
        result.fled = True
        battle.narrate(f"  {caster.name} escapes! ({chance:.0f}% chance)")
    else:
        battle.narrate(f"  {caster.name} fails to escape. ({chance:.0f}% chance)")
    return result

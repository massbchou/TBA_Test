"""Permanent, out-of-combat effects used by occurrences and level-up perks.

Each effect is a dict with a ``type`` plus parameters, e.g.
``{"type": "stat_change", "stat": "str", "value": 2}``. Register new effect
types with ``@register_effect``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from src.models.player import Player

Effect = Callable[["Player", dict[str, Any], Any], str]
EFFECTS: dict[str, Effect] = {}

# Parameters each effect type requires (used by data validation).
REQUIRED_PARAMS: dict[str, tuple[str, ...]] = {}


def register_effect(name: str, required: tuple[str, ...] = ()) -> Callable[[Effect], Effect]:
    def decorator(fn: Effect) -> Effect:
        EFFECTS[name] = fn
        REQUIRED_PARAMS[name] = required
        return fn
    return decorator


@register_effect("none")
def _none(player, effect, loader) -> str:
    return ""


@register_effect("stat_change", ("stat", "value"))
def _stat_change(player, effect, loader) -> str:
    stat, value = effect["stat"], effect["value"]
    player.modify_base_stat(stat, value)
    return f"Your {stat.upper()} changes by {value:+d}."


@register_effect("heal", ("amount",))
def _heal(player, effect, loader) -> str:
    healed = player.heal(int(effect["amount"]))
    return f"You recover {healed} HP. (HP {player.health}/{int(player.get_stat('max_health'))})"


@register_effect("restore", ("resource",))
def _restore(player, effect, loader) -> str:
    names = list(player.resources) if effect["resource"] == "all" else [effect["resource"].lower()]
    parts = []
    for name in names:
        res = player.resources.get(name)
        if res is None:
            continue
        amount = res.maximum if effect.get("amount", "full") == "full" else int(effect["amount"])
        parts.append(f"{player.restore_resource(name, amount)} {name.upper()}")
    return f"You restore {', '.join(parts)}." if parts else ""


@register_effect("gold", ("amount",))
def _gold(player, effect, loader) -> str:
    before = player.gold
    player.gold = max(0, player.gold + int(effect["amount"]))
    delta = player.gold - before
    return f"You {'gain' if delta >= 0 else 'lose'} {abs(delta)} gold. (Gold: {player.gold})"


@register_effect("item", ("item_id",))
def _item(player, effect, loader) -> str:
    qty = int(effect.get("quantity", 1))
    player.add_item(effect["item_id"], qty)
    name = effect["item_id"]
    if loader is not None and effect["item_id"] in getattr(loader, "items", {}):
        name = loader.items[effect["item_id"]].get("name", name)
    return f"You obtain {name} x{qty}."


def apply_effects(player: "Player", effects: list[dict[str, Any]], loader: Any = None) -> list[str]:
    """Applies effects in order and returns the non-empty result messages."""
    messages = []
    for effect in effects:
        fn = EFFECTS.get(effect.get("type", "none"))
        if fn is None:
            messages.append(f"(Unknown effect type {effect.get('type')!r} ignored.)")
            continue
        msg = fn(player, effect, loader)
        if msg:
            messages.append(msg)
    return messages

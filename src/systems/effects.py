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
    from src.stats import display_name

    stat, value = effect["stat"], effect["value"]
    player.modify_base_stat(stat, value)
    return f"{display_name(stat)} {value:+d} (now {int(player.get_stat(stat))})."


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
        restored = player.restore_resource(name, amount)
        if restored:
            parts.append(f"{restored} {name.title()}")
    return f"You restore {', '.join(parts)}." if parts else ""


@register_effect("gold", ("amount",))
def _gold(player, effect, loader) -> str:
    """Adds or removes gold. Spending is gated by a choice's ``requires``; this never goes below 0."""
    before = player.gold
    player.gold = max(0, player.gold + int(effect["amount"]))
    delta = player.gold - before
    if delta == 0:
        return ""
    verb = "receive" if delta > 0 else "pay"
    return f"You {verb} {abs(delta)} gold. (Gold: {player.gold})"


@register_effect("item", ("item_id",))
def _item(player, effect, loader) -> str:
    """Gives items; a negative ``quantity`` takes them (gate the choice with ``requires.item``)."""
    qty = int(effect.get("quantity", 1))
    name = effect["item_id"]
    if loader is not None and effect["item_id"] in getattr(loader, "items", {}):
        name = loader.items[effect["item_id"]].get("name", name)
    if qty < 0:
        taken = min(-qty, player.inventory.get(effect["item_id"], 0))
        player.remove_item(effect["item_id"], taken)
        return f"You hand over {name} x{taken}." if taken else ""
    player.add_item(effect["item_id"], qty)
    return f"You obtain {name} x{qty}."


@register_effect("hurt", ("amount",))
def _hurt(player, effect, loader) -> str:
    """Out-of-combat harm. It cannot kill: the player is left with at least 1 HP."""
    lost = min(int(effect["amount"]), player.health - 1)
    player.health -= max(0, lost)
    return f"You lose {max(0, lost)} HP. (HP {player.health}/{int(player.get_stat('max_health'))})"


@register_effect("learn_action", ("action_id",))
def _learn_action(player, effect, loader) -> str:
    action_id = effect["action_id"]
    action = loader.actions.get(action_id) if loader is not None else None
    if action is None:
        return f"(Unknown action {action_id!r}.)"
    known = player.spells if action.source == "spell" else player.abilities
    if action_id in known:
        return f"You already know {action.name}."
    known.append(action_id)
    return f"You learn {action.name}!"


@register_effect("exp", ("amount",))
def _exp(player, effect, loader) -> str:
    # Level-ups need the Combat system, so OccurrenceEvent handles this type itself.
    # ``amount`` may be a formula using ``floor`` (e.g. "10 + 6 * floor").
    return ""


@register_effect("combat", ("enemies",))
def _combat(player, effect, loader) -> str:
    # Combat needs the running Combat system, so OccurrenceEvent handles this type itself.
    return ""


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

"""Built-in target filters. Register new ones with ``@register_filter``."""
from __future__ import annotations

from typing import Any

from src.stats import HEALTH, RESOURCES, canonical_stat
from src.systems.actions.context import parse_literal
from src.systems.actions.registry import register_filter


def compare(left: Any, op: str, right: Any) -> bool:
    """Compares values; a missing (None) left side only satisfies ``!=``."""
    if left is None:
        return op == "!=" and right is not None
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        a, b = float(left), float(right)
        return {
            ">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b,
            "=": a == b, "==": a == b, "!=": a != b,
        }[op]
    a, b = str(left).lower(), str(right).lower()
    if op in ("=", "=="):
        return a == b
    if op == "!=":
        return a != b
    return False


@register_filter("WITH_TAG", 1)
def _with_tag(char, args, ctx) -> bool:
    return args[0].lower() in (t.lower() for t in char.tags)


@register_filter("WITH_STAT", 3)
def _with_stat(char, args, ctx) -> bool:
    name, op, raw = args
    key = canonical_stat(name)
    if raw.endswith("%"):
        pct = float(raw[:-1])
        if key == HEALTH:
            return compare(char.get_stat("hp_percentage"), op, pct)
        if key in RESOURCES:
            maximum = char.get_stat(f"max_{key}")
            current = char.get_stat(key)
            return compare((current / maximum * 100) if maximum else 0, op, pct)
        raw = raw[:-1]
    found, value = char.lookup(name)
    return compare(value if found else None, op, parse_literal(raw))


@register_filter("HAS_STATUS", 1)
def _has_status(char, args, ctx) -> bool:
    return char.has_status(args[0])


@register_filter("EXISTS_VARIABLE", 1)
def _exists_variable(char, args, ctx) -> bool:
    return char.has_variable(args[0])


@register_filter("IS_PLAYER", 0)
def _is_player(char, args, ctx) -> bool:
    return ctx.battle.is_player(char)


@register_filter("ALLY_COUNT", 2)
def _ally_count(char, args, ctx) -> bool:
    others = [c for c in ctx.battle.allies_of(char) if c is not char]
    return compare(len(others), args[0], parse_literal(args[1]))


@register_filter("ENEMY_COUNT", 2)
def _enemy_count(char, args, ctx) -> bool:
    return compare(len(ctx.battle.enemies_of(char)), args[0], parse_literal(args[1]))


@register_filter("ACTION_HAS_TAG", 1, subject="action")
def _action_has_tag(action, args, ctx) -> bool:
    return action.has_tag(args[0])

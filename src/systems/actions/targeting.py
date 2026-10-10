"""Target resolution: group pool -> filters -> quantity selection."""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.formula import evaluate_formula
from src.systems.actions.conditions import eval_filter
from src.systems.actions.nodes import Selector, TargetPhrase
from src.systems.ai import policy

if TYPE_CHECKING:
    from src.models.character import Character
    from src.systems.actions.context import ExecutionContext


def _pool(selector: Selector, ctx: "ExecutionContext") -> list["Character"]:
    battle = ctx.battle
    kind = selector.kind
    if kind == "base":
        if selector.group == "ENEMY":
            return battle.enemies_of(ctx.caster)
        return battle.allies_of(ctx.caster)
    if kind == "self":
        pool = [ctx.caster]
    elif kind == "player":
        pool = [battle.player]
    elif kind == "last_actor":
        pool = [battle.log.last_actor] if battle.log.last_actor is not None else []
    elif kind == "previous_targets":
        pool = list(ctx.line_targets.get(ctx.current_line - 1, []))
    elif kind == "all_targets_line":
        pool = list(ctx.line_targets.get(selector.line, []))
    elif kind == "specific_target":
        line = ctx.line_targets.get(selector.line, [])
        pool = [line[selector.index - 1]] if 0 < selector.index <= len(line) else []
    elif kind == "all_targets_so_far":
        pool = ctx.all_targets_so_far()
    else:
        raise ValueError(f"Unknown selector kind {kind!r}")
    return [c for c in pool if c.is_alive()]


def _quantity(selector: Selector, ctx: "ExecutionContext", pool_size: int) -> int:
    q = selector.quantity or "ALL"
    if q.upper() == "ALL":
        return pool_size
    if q.isdigit():
        return int(q)
    return int(evaluate_formula(q, rng=ctx.battle.rng))


def resolve_targets(phrase: TargetPhrase, ctx: "ExecutionContext", for_condition: bool = False) -> list["Character"]:
    """Resolves a targeting phrase.

    With ``for_condition`` the quantity and mode are ignored: an IF clause is true
    when at least one character survives the filters.
    """
    pool = _pool(phrase.selector, ctx)
    if phrase.filter is not None:
        pool = [c for c in pool if eval_filter(phrase.filter, c, ctx)]
    if for_condition or phrase.selector.kind != "base":
        return pool

    n = _quantity(phrase.selector, ctx, len(pool))
    if n >= len(pool):
        return pool
    if n <= 0:
        return []

    battle = ctx.battle
    if (phrase.mode or "RANDOM") == "CHOICE":
        if battle.is_player(ctx.caster):
            return _prompt(pool, n, ctx)
        ai_target = ctx.action.ai_target if ctx.action is not None else None
        return policy.select(ai_target, ctx.current_verb, pool, n, ctx.caster, battle.rng)
    return battle.rng.sample(pool, n)


def _prompt(pool: list["Character"], n: int, ctx: "ExecutionContext") -> list["Character"]:
    remaining = list(pool)
    picked: list["Character"] = []
    action_name = ctx.action.name if ctx.action is not None else ctx.current_verb
    for i in range(n):
        options = [f"{c.name} (HP {c.health}/{int(c.get_stat('max_health'))})" for c in remaining]
        suffix = f" ({i + 1}/{n})" if n > 1 else ""
        idx = ctx.battle.input.choose(f"Choose a target for {action_name}{suffix}:", options)
        picked.append(remaining.pop(idx))
    return picked

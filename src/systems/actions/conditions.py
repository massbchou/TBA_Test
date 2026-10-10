"""Evaluates conditions and filter expressions (shared by IF lines and AI scripts)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.systems.actions.nodes import (
    AbilityClause,
    ActionClause,
    CharClause,
    CondBinary,
    Condition,
    CondNot,
    FilterBinary,
    FilterExpr,
    FilterNot,
    FilterPred,
)
from src.systems.actions.registry import FILTERS

if TYPE_CHECKING:
    from src.systems.actions.context import ExecutionContext


def eval_condition(cond: Condition, ctx: "ExecutionContext") -> bool:
    from src.systems.actions.targeting import resolve_targets

    if isinstance(cond, CondBinary):
        if cond.op == "AND":
            return eval_condition(cond.left, ctx) and eval_condition(cond.right, ctx)
        return eval_condition(cond.left, ctx) or eval_condition(cond.right, ctx)
    if isinstance(cond, CondNot):
        return not eval_condition(cond.operand, ctx)
    if isinstance(cond, CharClause):
        return bool(resolve_targets(cond.phrase, ctx, for_condition=True))
    if isinstance(cond, ActionClause):
        action = ctx.battle.log.last_action
        return action is not None and eval_filter(cond.filter, action, ctx)
    if isinstance(cond, AbilityClause):
        caster = ctx.caster
        return caster.owns(cond.ability_id) and caster.is_ready(cond.ability_id)
    raise TypeError(f"Unknown condition node: {cond!r}")


def eval_filter(expr: FilterExpr, subject: Any, ctx: "ExecutionContext") -> bool:
    if isinstance(expr, FilterBinary):
        if expr.op == "AND":
            return eval_filter(expr.left, subject, ctx) and eval_filter(expr.right, subject, ctx)
        return eval_filter(expr.left, subject, ctx) or eval_filter(expr.right, subject, ctx)
    if isinstance(expr, FilterNot):
        return not eval_filter(expr.operand, subject, ctx)
    if isinstance(expr, FilterPred):
        return bool(FILTERS[expr.name].fn(subject, expr.args, ctx))
    raise TypeError(f"Unknown filter node: {expr!r}")

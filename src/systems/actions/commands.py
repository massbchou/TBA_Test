"""Built-in Action DSL commands. Register new verbs with ``@register_command``.

Handlers receive ``(ctx, targets, args, line_result)``. ``args`` are already
parsed: amounts are ``Amount`` nodes and durations are ``Duration`` nodes.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.models.character import PHYSICAL
from src.stats import canonical_stat, display_name
from src.systems.actions.context import parse_literal
from src.systems.actions.registry import register_command

if TYPE_CHECKING:
    from src.models.character import Character
    from src.systems.actions.context import ExecutionContext, LineResult


def _hp(char: "Character") -> str:
    return f"{char.health}/{int(char.get_stat('max_health'))}"


@register_command("DAMAGE", ["amount", "damage_type?"])
def damage(ctx: "ExecutionContext", targets, args, lr: "LineResult") -> None:
    dtype = (args[1] if len(args) > 1 else PHYSICAL).upper()
    battle = ctx.battle
    total = 0
    for target in targets:
        raw = ctx.eval_amount(args[0])
        dealt = target.apply_damage(raw, dtype, physical=battle.is_physical(dtype))
        lr.amounts[target.name] = lr.amounts.get(target.name, 0) + dealt
        total += dealt
        battle.narrate(f"  {target.name} takes {dealt} {dtype} damage. (HP {_hp(target)})")
        if not target.is_alive():
            battle.on_defeat(target)
        elif dealt > 0:
            battle.emit("on_damage_taken", target)
    ctx.previous_damage_dealt = total


@register_command("HEAL", ["amount"])
def heal(ctx: "ExecutionContext", targets, args, lr: "LineResult") -> None:
    for target in targets:
        healed = target.heal(ctx.eval_amount(args[0]))
        lr.amounts[target.name] = healed
        if healed > 0:
            ctx.battle.narrate(f"  {target.name} recovers {healed} HP. (HP {_hp(target)})")


def _modify(ctx: "ExecutionContext", targets, args, lr: "LineResult", sign: int) -> None:
    """Adds a timed stat modifier. Re-applying the same action's modifier refreshes it
    instead of stacking, unless the action is tagged ``stacks``."""
    stat = canonical_stat(args[0])
    source = ctx.action.id if ctx.action else ""
    stacks = ctx.action is not None and ctx.action.has_tag("stacks")
    for target in targets:
        amount = sign * ctx.eval_amount(args[1])
        timer = ctx.make_timer(args[2], target) if len(args) > 2 else None
        refreshed = False
        if source and not stacks:
            before = len(target.modifiers)
            target.modifiers = [m for m in target.modifiers if not (m.source == source and m.stat == stat)]
            refreshed = len(target.modifiers) < before
        target.add_modifier(stat, amount, timer, source=source)
        lr.amounts[target.name] = amount
        name = display_name(stat)
        if refreshed:
            ctx.battle.narrate(f"  {target.name}'s {name} {'boost' if amount >= 0 else 'penalty'} is renewed.")
        else:
            ctx.battle.narrate(f"  {target.name}'s {name} {'rises' if amount >= 0 else 'falls'} by {abs(amount)}.")


@register_command("BUFF", ["stat", "amount", "duration?"])
def buff(ctx, targets, args, lr) -> None:
    _modify(ctx, targets, args, lr, +1)


@register_command("DEBUFF", ["stat", "amount", "duration?"])
def debuff(ctx, targets, args, lr) -> None:
    _modify(ctx, targets, args, lr, -1)


@register_command("APPLY", ["status", "duration?"])
def apply_status(ctx: "ExecutionContext", targets, args, lr: "LineResult") -> None:
    name = args[0].upper()
    status_def = ctx.battle.statuses.get(name)
    stacking = status_def.stacking if status_def else "refresh"
    for target in targets:
        timer = ctx.make_timer(args[1], target) if len(args) > 1 else None
        outcome = target.add_status(name, timer, stacking, source=ctx.caster)
        lr.amounts[target.name] = 1 if outcome != "ignored" else 0
        if outcome == "ignored":
            continue
        if outcome == "applied":
            is_buff = status_def is not None and "buff" in status_def.tags
            ctx.battle.narrate(f"  {target.name} {'gains' if is_buff else 'is afflicted with'} {name}.")
        else:
            ctx.battle.narrate(f"  {target.name}'s {name} is {outcome}.")
        status = target.get_status(name)
        if status is not None:
            ctx.battle.run_status_hook(target, status, "on_apply")


@register_command("SET", ["name", "value", "duration?"])
def set_variable(ctx: "ExecutionContext", targets, args, lr: "LineResult") -> None:
    value = parse_literal(args[1])
    for target in targets:
        timer = ctx.make_timer(args[2], target) if len(args) > 2 else None
        target.set_variable(args[0], value, timer)
        lr.amounts[target.name] = 1


@register_command("RESTORE", ["resource", "amount"])
def restore(ctx: "ExecutionContext", targets, args, lr: "LineResult") -> None:
    resource = args[0].lower()
    for target in targets:
        restored = target.restore_resource(resource, ctx.eval_amount(args[1]))
        lr.amounts[target.name] = restored
        if restored > 0:
            ctx.battle.narrate(f"  {target.name} restores {restored} {display_name(resource)}.")


@register_command("CLEANSE", ["status_or_all"])
def cleanse(ctx: "ExecutionContext", targets, args, lr: "LineResult") -> None:
    which = args[0].upper()
    statuses = ctx.battle.statuses
    for target in targets:
        if which == "ALL_DEBUFFS":
            removed = target.remove_statuses(
                lambda s: s.name in statuses and "debuff" in statuses[s.name].tags
            )
            names = [s.name for s in removed]
            negative = [m for m in target.modifiers if m.amount < 0]
            target.modifiers = [m for m in target.modifiers if m.amount >= 0]
            names += [f"-{m.stat.upper()}" for m in negative]
        else:
            names = [which] if target.remove_status(which) else []
        lr.amounts[target.name] = len(names)
        if names:
            ctx.battle.narrate(f"  {target.name} is cleansed of {', '.join(names)}.")


def _gold_holders(targets):
    return [t for t in targets if hasattr(t, "gold")]


@register_command("GAIN_GOLD", ["amount"])
def gain_gold(ctx: "ExecutionContext", targets, args, lr: "LineResult") -> None:
    for target in _gold_holders(targets):
        amount = max(0, ctx.eval_amount(args[0]))
        target.gold += amount
        lr.amounts[target.name] = amount
        ctx.battle.narrate(f"  {target.name} pockets {amount} gold.")


@register_command("LOSE_GOLD", ["amount"])
def lose_gold(ctx: "ExecutionContext", targets, args, lr: "LineResult") -> None:
    for target in _gold_holders(targets):
        amount = min(target.gold, max(0, ctx.eval_amount(args[0])))
        target.gold -= amount
        lr.amounts[target.name] = amount
        if hasattr(ctx.caster, "stolen_gold"):
            ctx.caster.stolen_gold += amount  # recovered if the thief is defeated
        if amount:
            ctx.battle.narrate(f"  {target.name} loses {amount} gold!")

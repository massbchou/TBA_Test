"""Runs a parsed Program line by line, honouring IF and DELAY."""
from __future__ import annotations

import logging

from src.formula import FormulaError
from src.systems.actions.conditions import eval_condition
from src.systems.actions.context import ActionRuntimeError, ExecutionContext, LineResult
from src.systems.actions.nodes import ActionLine
from src.systems.actions.registry import COMMANDS
from src.systems.actions.targeting import resolve_targets

logger = logging.getLogger("textrogue.actions")


def run_program(ctx: ExecutionContext, start: int = 0) -> None:
    lines = ctx.program.lines
    for index in range(start, len(lines)):
        line = lines[index]
        if line.delay is not None:
            _schedule(line, index, ctx)
            if line.delay.mode == "BLOCKING":
                return
            continue
        run_line(line, ctx)


def _schedule(line: ActionLine, index: int, ctx: ExecutionContext) -> None:
    blocking = line.delay.mode == "BLOCKING"

    def fire() -> None:
        if not ctx.caster.is_alive():
            return
        run_line(line, ctx)
        if blocking:
            run_program(ctx, index + 1)

    ctx.result.lines.append(LineResult(line.number, line.verb, delayed=True))
    amount = ctx.eval_amount(line.delay.amount)
    battle = ctx.battle
    if amount <= 0:
        fire()
    elif line.delay.unit == "TURNS":
        battle.scheduler.after_turns(ctx.caster, amount, fire)
    else:
        length = battle.round_length if line.delay.unit == "ROUNDS" else 1
        battle.scheduler.at_clock(ctx.caster, battle.clock + amount * length, fire)


def run_line(line: ActionLine, ctx: ExecutionContext) -> LineResult:
    ctx.current_line = line.number
    ctx.current_verb = line.verb
    lr = LineResult(line.number, line.verb)
    ctx.result.lines.append(lr)
    ctx.line_targets[line.number] = []
    try:
        if line.condition is not None and not eval_condition(line.condition, ctx):
            lr.skipped_reason = "condition false"
            return lr
        targets = resolve_targets(line.target, ctx)
        ctx.line_targets[line.number] = targets
        lr.targets = [t.name for t in targets]
        if not targets:
            lr.skipped_reason = "no targets"
            return lr
        COMMANDS[line.verb].handler(ctx, targets, line.args, lr)
        for target in targets:
            if not any(target is a for a in ctx.result.affected):
                ctx.result.affected.append(target)
    except (FormulaError, ActionRuntimeError, KeyError, ValueError) as exc:
        lr.skipped_reason = f"error: {exc}"
        logger.warning("Skipping line %d (%r): %s", line.number, line.text, exc)
    return lr

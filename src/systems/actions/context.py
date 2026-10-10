"""Execution context and structured results for one action."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from src.formula import evaluate_formula
from src.models.character import Timer
from src.systems.actions.nodes import Amount, Duration, Program

if TYPE_CHECKING:
    from src.models.character import Character
    from src.systems.actions.definitions import ActionDef
    from src.systems.battle import Battle


class ActionRuntimeError(Exception):
    """A line failed at runtime; it is skipped with a warning."""


@dataclass
class LineResult:
    line: int
    verb: str
    targets: list[str] = field(default_factory=list)
    amounts: dict[str, int] = field(default_factory=dict)
    skipped_reason: str | None = None
    delayed: bool = False


@dataclass
class ActionResult:
    action_id: str
    caster: str
    lines: list[LineResult] = field(default_factory=list)
    affected: list["Character"] = field(default_factory=list)
    fled: bool = False

    def total(self, verb: str) -> int:
        return sum(sum(lr.amounts.values()) for lr in self.lines if lr.verb == verb)

    def amount_to(self, target_name: str, verb: str) -> int:
        return sum(lr.amounts.get(target_name, 0) for lr in self.lines if lr.verb == verb)


@dataclass
class ExecutionContext:
    caster: "Character"
    battle: "Battle"
    action: "ActionDef | None"
    program: Program
    result: ActionResult
    line_targets: dict[int, list["Character"]] = field(default_factory=dict)
    previous_damage_dealt: int = 0
    current_line: int = 0
    current_verb: str = ""

    def resolve_number(self, name: str) -> float:
        if name.upper() == "PREVIOUS_DAMAGE_DEALT":
            return float(self.previous_damage_dealt)
        return self.caster.formula_value(name)

    def eval_amount(self, amount: Amount) -> int:
        if amount.kind == "int":
            return amount.value
        if amount.kind == "range":
            return self.battle.rng.randint(amount.low, amount.high)
        return int(evaluate_formula(amount.text, resolver=self.resolve_number, rng=self.battle.rng))

    def make_timer(self, duration: Duration, bearer: "Character") -> Timer:
        count = self.eval_amount(duration.amount)
        if duration.unit == "TURNS":
            return Timer("TURNS", remaining=count, applied_turn=bearer.turn_count)
        length = self.battle.round_length if duration.unit == "ROUNDS" else 1
        return Timer("CLOCK", expires_at=self.battle.clock + count * length)

    def all_targets_so_far(self) -> list["Character"]:
        seen: list["Character"] = []
        for number in sorted(self.line_targets):
            for target in self.line_targets[number]:
                if not any(target is s for s in seen):
                    seen.append(target)
        return seen


def parse_literal(text: str) -> Any:
    """Parses a SET / WITH_STAT value: bool, int, float, or string."""
    lowered = text.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "none"):
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text

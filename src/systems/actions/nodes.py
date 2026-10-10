"""AST node types for Action Strings and conditions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Union


@dataclass
class Diagnostic:
    severity: str  # "error" | "warning" | "info"
    message: str
    line: int | None = None
    source: str = ""

    def __str__(self) -> str:
        where = self.source + (f" line {self.line}" if self.line is not None else "")
        return f"[{self.severity}] {where}: {self.message}" if where else f"[{self.severity}] {self.message}"


@dataclass
class Amount:
    """A number, a ``low-high`` range, or a formula (which may contain dice)."""
    kind: str  # "int" | "range" | "formula"
    text: str
    value: int = 0
    low: int = 0
    high: int = 0


@dataclass
class Duration:
    unit: str  # "TURNS" | "ROUNDS" | "TIME_UNITS"
    amount: Amount


@dataclass
class Selector:
    # base | self | player | last_actor | previous_targets | all_targets_line
    # | specific_target | all_targets_so_far
    kind: str
    quantity: str | None = None  # base only: "ALL", "2", "1d3"
    group: str | None = None     # base only: "ENEMY" | "ALLY"
    line: int = 0
    index: int = 0


@dataclass
class FilterPred:
    name: str
    args: list[str]


@dataclass
class FilterNot:
    operand: "FilterExpr"


@dataclass
class FilterBinary:
    op: str  # "AND" | "OR"
    left: "FilterExpr"
    right: "FilterExpr"


FilterExpr = Union[FilterPred, FilterNot, FilterBinary]


@dataclass
class TargetPhrase:
    selector: Selector
    mode: str | None = None  # "CHOICE" | "RANDOM" | None
    filter: FilterExpr | None = None


@dataclass
class CharClause:
    phrase: TargetPhrase


@dataclass
class ActionClause:
    subject: str  # "LAST_ACTION"
    filter: FilterExpr


@dataclass
class AbilityClause:
    ability_id: str


@dataclass
class CondNot:
    operand: "Condition"


@dataclass
class CondBinary:
    op: str
    left: "Condition"
    right: "Condition"


Condition = Union[CharClause, ActionClause, AbilityClause, CondNot, CondBinary]


@dataclass
class Delay:
    mode: str  # "BLOCKING" | "NONBLOCKING"
    unit: str  # "TURNS" | "ROUNDS" | "TIME_UNITS"
    amount: Amount


@dataclass
class ActionLine:
    number: int
    text: str
    verb: str
    target: TargetPhrase
    args: list[Any] = field(default_factory=list)
    delay: Delay | None = None
    condition: Condition | None = None


@dataclass
class Program:
    """A parsed Action String. Malformed lines are dropped into ``diagnostics``."""
    lines: list[ActionLine] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def errors(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == "error"]

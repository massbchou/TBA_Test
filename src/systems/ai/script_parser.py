"""Parser and evaluator for Attack Script lines (docs/ai_scripts.md).

    stmt := use_ability <id>
          | WEIGHTED_CHOICE ( "{" WEIGHT <n> ":" stmt "}" )+
          | CHANCE <0-100> "{" stmt "}"
          | IF cond "{" stmt "}" ( ELSE IF cond "{" stmt "}" )* [ ELSE "{" stmt "}" ]

Conditions use the Action System condition grammar. An empty block ``{ }`` is a
blank line. Evaluating a statement yields an ability id, or None for "blank".
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Union

from src.systems.actions.conditions import eval_condition
from src.systems.actions.lexer import COLON, LBRACE, RBRACE, strip_comment, tokenize
from src.systems.actions.nodes import Condition, Diagnostic
from src.systems.actions.parser import ParseError, TokenStream, parse_condition, parse_condition_text
from src.utils import weighted_choice

if TYPE_CHECKING:
    from src.systems.actions.context import ExecutionContext


@dataclass
class UseAbility:
    ability_id: str


@dataclass
class WeightedChoice:
    options: list[tuple[int, "Stmt | None"]]


@dataclass
class Chance:
    percent: float
    body: "Stmt | None"


@dataclass
class IfChain:
    branches: list[tuple[Condition, "Stmt | None"]]
    otherwise: "Stmt | None" = None


Stmt = Union[UseAbility, WeightedChoice, Chance, IfChain]


@dataclass
class Script:
    condition: Condition | None
    interruptible: bool
    lines: list[Stmt] = field(default_factory=list)
    condition_valid: bool = True

    def is_active(self, ctx: "ExecutionContext") -> bool:
        if not self.condition_valid:
            return False
        return self.condition is None or eval_condition(self.condition, ctx)


def _braced(ts: TokenStream) -> Stmt | None:
    ts.expect(LBRACE)
    tok = ts.peek()
    if tok is not None and tok.kind == RBRACE:
        ts.next()
        return None
    stmt = _stmt(ts)
    ts.expect(RBRACE)
    return stmt


def _stmt(ts: TokenStream) -> Stmt:
    word = ts.peek_word()
    if word == "USE_ABILITY":
        ts.next()
        return UseAbility(ts.next_word("an ability id").text)
    if word == "WEIGHTED_CHOICE":
        ts.next()
        options: list[tuple[int, Stmt | None]] = []
        while ts.peek() is not None and ts.peek().kind == LBRACE:
            ts.next()
            if ts.next_word("WEIGHT").upper != "WEIGHT":
                raise ParseError("Expected WEIGHT inside WEIGHTED_CHOICE option")
            weight_text = ts.next_word("a weight").text
            if not weight_text.isdigit():
                raise ParseError(f"Invalid weight '{weight_text}'")
            ts.expect(COLON)
            tok = ts.peek()
            body = None if tok is not None and tok.kind == RBRACE else _stmt(ts)
            ts.expect(RBRACE)
            options.append((int(weight_text), body))
        if not options:
            raise ParseError("WEIGHTED_CHOICE needs at least one { WEIGHT n: action } option")
        return WeightedChoice(options)
    if word == "CHANCE":
        ts.next()
        pct_text = ts.next_word("a percentage").text
        try:
            pct = float(pct_text)
        except ValueError:
            raise ParseError(f"Invalid CHANCE percentage '{pct_text}'") from None
        return Chance(pct, _braced(ts))
    if word == "IF":
        ts.next()
        branches = [(parse_condition(ts), _braced(ts))]
        otherwise = None
        while ts.peek_word() == "ELSE":
            ts.next()
            if ts.peek_word() == "IF":
                ts.next()
                branches.append((parse_condition(ts), _braced(ts)))
            else:
                otherwise = _braced(ts)
                break
        return IfChain(branches, otherwise)
    tok = ts.peek()
    raise ParseError(f"Unknown script statement '{tok.text if tok else ''}'")


def parse_script_line(text: str) -> Stmt | None:
    """Parses one script line. Returns None for a blank line; raises ParseError if malformed."""
    if not strip_comment(text):
        return None
    ts = TokenStream(tokenize(text))
    stmt = _stmt(ts)
    if not ts.at_end:
        raise ParseError(f"Unexpected '{ts.peek().text}' after statement")
    return stmt


def parse_scripts(data: list[dict[str, Any]], source: str = "") -> tuple[list[Script], list[Diagnostic]]:
    """Parses an enemy's attack_scripts. Blank and malformed lines are dropped."""
    scripts: list[Script] = []
    diagnostics: list[Diagnostic] = []
    for i, raw in enumerate(data):
        where = f"{source} script {i}"
        cond = None
        valid = True
        cond_text = (raw.get("activation_condition") or "").strip()
        if cond_text:
            try:
                cond = parse_condition_text(cond_text)
            except ParseError as exc:
                valid = False
                diagnostics.append(Diagnostic("error", f"activation_condition: {exc}", source=where))
        script = Script(cond, bool(raw.get("interruptible", True)), condition_valid=valid)
        for n, line in enumerate(raw.get("script_lines", []), start=1):
            try:
                stmt = parse_script_line(line)
            except ParseError as exc:
                diagnostics.append(Diagnostic("error", f"{exc} :: {line!r}", n, where))
                continue
            if stmt is not None:
                script.lines.append(stmt)
        scripts.append(script)
    return scripts, diagnostics


def referenced_abilities(stmt: Stmt | None) -> list[str]:
    """Every ability id a statement could use (for data validation)."""
    if stmt is None:
        return []
    if isinstance(stmt, UseAbility):
        return [stmt.ability_id]
    if isinstance(stmt, WeightedChoice):
        return [a for _, body in stmt.options for a in referenced_abilities(body)]
    if isinstance(stmt, Chance):
        return referenced_abilities(stmt.body)
    ids = [a for _, body in stmt.branches for a in referenced_abilities(body)]
    return ids + referenced_abilities(stmt.otherwise)


def evaluate(stmt: Stmt | None, ctx: "ExecutionContext", rng: random.Random) -> str | None:
    """Resolves a statement to an ability id, or None if it comes out blank."""
    if stmt is None:
        return None
    if isinstance(stmt, UseAbility):
        return stmt.ability_id
    if isinstance(stmt, WeightedChoice):
        index = weighted_choice({i: w for i, (w, _) in enumerate(stmt.options)}, rng=rng)
        return None if index is None else evaluate(stmt.options[index][1], ctx, rng)
    if isinstance(stmt, Chance):
        return evaluate(stmt.body, ctx, rng) if rng.uniform(0, 100) < stmt.percent else None
    for cond, body in stmt.branches:
        if eval_condition(cond, ctx):
            return evaluate(body, ctx, rng)
    return evaluate(stmt.otherwise, ctx, rng)

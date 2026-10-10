"""Recursive-descent parser for Action Strings and conditions.

Line grammar (see docs/action_system.md):

    line      := [DELAY mode unit amount] [IF condition] VERB target params*
    condition := or ; or := and (OR and)* ; and := not (AND not)*
    not       := NOT not | "(" or ")" | clause
    clause    := ABILITY <id> IS_READY | LAST_ACTION filters | target
    target    := selector [CHOICE|RANDOM] [filters] [CHOICE|RANDOM]
    filters   := f_or ; f_or := f_and (OR f_and)* ; f_and := f_not (AND f_not)*
    f_not     := NOT f_not | "(" f_or ")" | FILTER arg{arity}

Filters have fixed arity, so the parser knows where a targeting phrase ends and
the parameters begin. An ``AND``/``OR`` followed by a subject keyword (SELF,
PLAYER, LAST_ACTOR, LAST_ACTION, ABILITY, a base selector...) starts a new
condition clause instead of joining filters.
"""
from __future__ import annotations

import re

# Importing these modules registers the built-in commands and filters.
from src.systems.actions import commands as _commands  # noqa: F401
from src.systems.actions import filters as _filters  # noqa: F401
from src.formula import validate_formula
from src.stats import is_known_stat
from src.systems.actions.lexer import LPAREN, RPAREN, WORD, Token, strip_comment, tokenize
from src.systems.actions.nodes import (
    AbilityClause,
    ActionClause,
    ActionLine,
    Amount,
    CharClause,
    CondBinary,
    Condition,
    CondNot,
    Delay,
    Diagnostic,
    Duration,
    FilterBinary,
    FilterExpr,
    FilterNot,
    FilterPred,
    Program,
    Selector,
    TargetPhrase,
)
from src.systems.actions.registry import COMMANDS, FILTERS

CONTEXT_VARIABLES = {"PREVIOUS_DAMAGE_DEALT"}
SIMPLE_SELECTORS = {"SELF", "PLAYER", "LAST_ACTOR", "PREVIOUS_TARGETS", "ALL_TARGETS_SO_FAR"}
SUBJECT_WORDS = SIMPLE_SELECTORS | {"LAST_ACTION", "ABILITY", "SPECIFIC_TARGET"}
POSITIONAL = {"LEFT_OF", "RIGHT_OF", "ADJACENT_TO"}
MODES = {"CHOICE", "RANDOM"}
COMPARATORS = {">", "<", ">=", "<=", "=", "==", "!="}
DELAY_MODES = {"BLOCKING", "NONBLOCKING"}

BASE_RE = re.compile(r"^(\d+|ALL|\d+D\d+)_(ENEMY|ENEMIES|ALLY|ALLIES)$")
LINE_REF_RE = re.compile(r"^ALL_TARGETS_LINE(\d+)$")
SPECIFIC_RE = re.compile(r"^TARGET(\d+)\.(\d+)$", re.IGNORECASE)
DURATION_RE = re.compile(r"^(\d+|\d+[dD]\d+)_(TURN|TURNS|ROUND|ROUNDS|TIME_UNIT|TIME_UNITS)$", re.IGNORECASE)
INT_RE = re.compile(r"^-?\d+$")
RANGE_RE = re.compile(r"^(\d+)-(\d+)$")

_UNITS = {
    "TURN": "TURNS", "TURNS": "TURNS",
    "ROUND": "ROUNDS", "ROUNDS": "ROUNDS",
    "TIME_UNIT": "TIME_UNITS", "TIME_UNITS": "TIME_UNITS",
}


class ParseError(Exception):
    """Raised for a malformed line; the line is dropped with a diagnostic."""


# --------------------------------------------------------------------- values

def _known_formula_name(name: str) -> bool:
    return is_known_stat(name) or name.upper() in CONTEXT_VARIABLES


def parse_amount(text: str) -> Amount:
    """Resolves an amount token: integer, then ``low-high`` range, then formula."""
    if INT_RE.match(text):
        return Amount("int", text, value=int(text))
    rng = RANGE_RE.match(text)
    if rng:
        low, high = int(rng.group(1)), int(rng.group(2))
        if low > high:
            raise ParseError(f"Range '{text}' has low > high")
        return Amount("range", text, low=low, high=high)
    error = validate_formula(text, _known_formula_name)
    if error:
        raise ParseError(f"Invalid amount '{text}': {error}")
    return Amount("formula", text)


def parse_duration(text: str) -> Duration:
    match = DURATION_RE.match(text)
    if not match:
        raise ParseError(f"Invalid duration '{text}' (expected e.g. 3_TURNS, 1d3_ROUNDS)")
    return Duration(_UNITS[match.group(2).upper()], parse_amount(match.group(1)))


# --------------------------------------------------------------------- stream

class TokenStream:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self, offset: int = 0) -> Token | None:
        i = self.pos + offset
        return self.tokens[i] if i < len(self.tokens) else None

    def peek_word(self, offset: int = 0) -> str | None:
        tok = self.peek(offset)
        return tok.upper if tok is not None and tok.kind == WORD else None

    def next(self) -> Token:
        tok = self.peek()
        if tok is None:
            raise ParseError("Unexpected end of line")
        self.pos += 1
        return tok

    def next_word(self, what: str = "a word") -> Token:
        tok = self.next()
        if tok.kind != WORD:
            raise ParseError(f"Expected {what}, got '{tok.text}'")
        return tok

    def expect(self, kind: str) -> Token:
        tok = self.next()
        if tok.kind != kind:
            raise ParseError(f"Expected '{'(' if kind == LPAREN else ')' if kind == RPAREN else kind}', got '{tok.text}'")
        return tok

    @property
    def at_end(self) -> bool:
        return self.pos >= len(self.tokens)


def is_subject_word(word: str | None) -> bool:
    if word is None:
        return False
    return (
        word in SUBJECT_WORDS
        or word in POSITIONAL
        or bool(BASE_RE.match(word))
        or bool(LINE_REF_RE.match(word))
    )


# ---------------------------------------------------------------- conditions

def parse_condition(ts: TokenStream) -> Condition:
    return _cond_or(ts)


def _cond_or(ts: TokenStream) -> Condition:
    left = _cond_and(ts)
    while ts.peek_word() == "OR" and _starts_clause(ts, 1):
        ts.next()
        left = CondBinary("OR", left, _cond_and(ts))
    return left


def _cond_and(ts: TokenStream) -> Condition:
    left = _cond_not(ts)
    while ts.peek_word() == "AND" and _starts_clause(ts, 1):
        ts.next()
        left = CondBinary("AND", left, _cond_not(ts))
    return left


def _starts_clause(ts: TokenStream, offset: int) -> bool:
    tok = ts.peek(offset)
    if tok is None:
        return False
    if tok.kind == LPAREN:
        return True
    return tok.kind == WORD and (tok.upper == "NOT" or is_subject_word(tok.upper))


def _cond_not(ts: TokenStream) -> Condition:
    if ts.peek_word() == "NOT":
        ts.next()
        return CondNot(_cond_not(ts))
    tok = ts.peek()
    if tok is not None and tok.kind == LPAREN:
        ts.next()
        inner = _cond_or(ts)
        ts.expect(RPAREN)
        return inner
    return _clause(ts)


def _clause(ts: TokenStream) -> Condition:
    word = ts.peek_word()
    if word == "ABILITY":
        ts.next()
        ability_id = ts.next_word("an ability id").text
        if ts.peek_word() != "IS_READY":
            raise ParseError("Expected IS_READY after ABILITY <id>")
        ts.next()
        return AbilityClause(ability_id)
    if word == "LAST_ACTION":
        ts.next()
        expr = parse_filter_expr(ts, "action")
        if expr is None:
            raise ParseError("LAST_ACTION must be followed by an action filter such as ACTION_HAS_TAG")
        return ActionClause("LAST_ACTION", expr)
    return CharClause(parse_target_phrase(ts))


# ------------------------------------------------------------------ targeting

def parse_target_phrase(ts: TokenStream) -> TargetPhrase:
    tok = ts.next_word("a target selector")
    word = tok.upper
    if word in POSITIONAL:
        raise ParseError(f"Positional selector {word} is unsupported (no battlefield positions yet)")
    if word in SIMPLE_SELECTORS:
        selector = Selector(word.lower())
    elif word == "SPECIFIC_TARGET":
        ref = ts.next_word("a target reference like target1.1").text
        match = SPECIFIC_RE.match(ref)
        if not match:
            raise ParseError(f"Invalid SPECIFIC_TARGET reference '{ref}' (expected target<L>.<I>)")
        selector = Selector("specific_target", line=int(match.group(1)), index=int(match.group(2)))
    elif LINE_REF_RE.match(word):
        selector = Selector("all_targets_line", line=int(LINE_REF_RE.match(word).group(1)))
    elif BASE_RE.match(word):
        match = BASE_RE.match(word)
        group = "ENEMY" if match.group(2).startswith("ENEM") else "ALLY"
        selector = Selector("base", quantity=match.group(1), group=group)
    else:
        raise ParseError(f"Expected a target selector, got '{tok.text}'")

    mode = None
    if ts.peek_word() in MODES:
        mode = ts.next().upper
    expr = parse_filter_expr(ts, "character")
    if mode is None and ts.peek_word() in MODES:
        mode = ts.next().upper
    return TargetPhrase(selector, mode, expr)


def _starts_filter(ts: TokenStream, offset: int, subject: str) -> bool:
    tok = ts.peek(offset)
    if tok is None:
        return False
    if tok.kind == LPAREN:
        return _starts_filter(ts, offset + 1, subject)
    if tok.kind != WORD:
        return False
    if tok.upper == "NOT":
        return _starts_filter(ts, offset + 1, subject)
    spec = FILTERS.get(tok.upper)
    return spec is not None and spec.subject == subject


def parse_filter_expr(ts: TokenStream, subject: str) -> FilterExpr | None:
    if not _starts_filter(ts, 0, subject):
        return None
    return _f_or(ts, subject)


def _f_or(ts: TokenStream, subject: str) -> FilterExpr:
    left = _f_and(ts, subject)
    while ts.peek_word() == "OR" and _starts_filter(ts, 1, subject):
        ts.next()
        left = FilterBinary("OR", left, _f_and(ts, subject))
    return left


def _f_and(ts: TokenStream, subject: str) -> FilterExpr:
    left = _f_not(ts, subject)
    while ts.peek_word() == "AND" and _starts_filter(ts, 1, subject):
        ts.next()
        left = FilterBinary("AND", left, _f_not(ts, subject))
    return left


def _f_not(ts: TokenStream, subject: str) -> FilterExpr:
    if ts.peek_word() == "NOT":
        ts.next()
        return FilterNot(_f_not(ts, subject))
    tok = ts.peek()
    if tok is not None and tok.kind == LPAREN:
        ts.next()
        inner = _f_or(ts, subject)
        ts.expect(RPAREN)
        return inner
    name = ts.next_word("a filter").upper
    spec = FILTERS.get(name)
    if spec is None or spec.subject != subject:
        raise ParseError(f"Unknown {subject} filter '{name}'")
    args = [ts.next_word(f"an argument for {name}").text for _ in range(spec.arity)]
    if name in ("WITH_STAT",) and args[1] not in COMPARATORS:
        raise ParseError(f"Invalid comparison operator '{args[1]}' in WITH_STAT")
    if name in ("ALLY_COUNT", "ENEMY_COUNT") and args[0] not in COMPARATORS:
        raise ParseError(f"Invalid comparison operator '{args[0]}' in {name}")
    return FilterPred(name, args)


# ---------------------------------------------------------------------- lines

def _parse_delay(ts: TokenStream) -> Delay:
    ts.next()  # DELAY
    mode = ts.next_word("BLOCKING or NONBLOCKING").upper
    if mode not in DELAY_MODES:
        raise ParseError(f"DELAY mode must be BLOCKING or NONBLOCKING, got '{mode}'")
    unit_tok = ts.next_word("a delay unit").text
    if unit_tok.upper() in _UNITS:
        amount = parse_amount(ts.next_word("a delay amount").text)
        return Delay(mode, _UNITS[unit_tok.upper()], amount)
    duration = parse_duration(unit_tok)
    return Delay(mode, duration.unit, duration.amount)


def _parse_param(kind: str, text: str):
    kind = kind.rstrip("?")
    if kind == "amount":
        return parse_amount(text)
    if kind == "duration":
        return parse_duration(text)
    return text


def parse_line(text: str, number: int = 1) -> ActionLine:
    ts = TokenStream(tokenize(text))
    if ts.at_end:
        raise ParseError("Empty line")
    delay = None
    condition = None
    if ts.peek_word() == "DELAY":
        delay = _parse_delay(ts)
    if ts.peek_word() == "IF":
        ts.next()
        condition = parse_condition(ts)
    if ts.peek_word() == "DELAY":
        raise ParseError("DELAY must come before IF")

    verb_tok = ts.next_word("a command")
    verb = verb_tok.upper
    spec = COMMANDS.get(verb)
    if spec is None:
        raise ParseError(f"Unknown command '{verb_tok.text}'")
    target = parse_target_phrase(ts)

    raw_params: list[str] = []
    while not ts.at_end:
        tok = ts.next()
        if tok.kind != WORD:
            raise ParseError(f"Unexpected '{tok.text}' in parameters")
        raw_params.append(tok.text)
    if not spec.required <= len(raw_params) <= len(spec.params):
        expected = " ".join(spec.params)
        raise ParseError(f"{verb} expects parameters [{expected}], got {len(raw_params)}: {raw_params}")
    args = [_parse_param(kind, value) for kind, value in zip(spec.params, raw_params)]
    return ActionLine(number, strip_comment(text), verb, target, args, delay, condition)


def parse_program(text: str, source: str = "") -> Program:
    """Parses a multi-line Action String. Line numbers count non-blank lines, from 1."""
    program = Program()
    number = 0
    for raw in (text or "").splitlines():
        if not strip_comment(raw):
            continue
        number += 1
        try:
            program.lines.append(parse_line(raw, number))
        except ParseError as exc:
            program.diagnostics.append(Diagnostic("error", f"{exc} :: {strip_comment(raw)!r}", number, source))
    return program


def parse_condition_text(text: str) -> Condition:
    """Parses a standalone condition such as an Attack Script activation_condition.

    A leading ``IF`` is optional.
    """
    ts = TokenStream(tokenize(text))
    if ts.peek_word() == "IF":
        ts.next()
    if ts.at_end:
        raise ParseError("Empty condition")
    cond = parse_condition(ts)
    if not ts.at_end:
        raise ParseError(f"Unexpected '{ts.peek().text}' after condition")
    return cond

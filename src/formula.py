"""Safe mathematical formula evaluator.

Replaces eval() for formulas like "base_exp * (1.1 ** (level - 1))".
Supports: +, -, *, /, **, unary +/-, parentheses, floating/integer numbers,
dice atoms (``2d10``, rolled at evaluation time), and variables.

Variables come either from keyword arguments (case-insensitive) or from a
``resolver`` callable, which lets callers expose character stats lazily.
"""
from __future__ import annotations

import random
import re
from typing import Any, Callable

_TOKEN_RE = re.compile(r"\s*(?:(\d+[dD]\d+)|(\d+\.?\d*)|(\*\*|[+\-*/()])|([a-zA-Z_]\w*))\s*")
_DICE_RE = re.compile(r"^(\d+)[dD](\d+)$")

Resolver = Callable[[str], float]


class FormulaError(ValueError):
    """Raised when formula evaluation fails."""
    pass


def _tokenize(expr: str) -> list[str]:
    pos = 0
    tokens: list[str] = []
    while pos < len(expr):
        match = _TOKEN_RE.match(expr, pos)
        if not match:
            raise FormulaError(f"Unexpected character in formula at position {pos}: {expr[pos:]!r}")
        token = match.group(1) or match.group(2) or match.group(3) or match.group(4)
        tokens.append(token)
        pos = match.end()
    return tokens


class _Parser:
    def __init__(
        self,
        tokens: list[str],
        variables: dict[str, float],
        resolver: Resolver | None = None,
        rng: random.Random | None = None,
    ):
        self.tokens = tokens
        self.variables = variables
        self.lowered = {k.lower(): v for k, v in variables.items()}
        self.resolver = resolver
        self.rng = rng or random
        self.pos = 0

    def _peek(self) -> str | None:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def _consume(self) -> str:
        tok = self._peek()
        if tok is None:
            raise FormulaError("Unexpected end of expression")
        self.pos += 1
        return tok

    def parse(self) -> float:
        res = self._expr()
        if self.pos < len(self.tokens):
            raise FormulaError(f"Unexpected token '{self.tokens[self.pos]}' at position {self.pos}")
        return res

    def _expr(self) -> float:
        val = self._term()
        while self._peek() in ("+", "-"):
            op = self._consume()
            right = self._term()
            if op == "+":
                val += right
            else:
                val -= right
        return val

    def _term(self) -> float:
        val = self._power()
        while self._peek() in ("*", "/"):
            op = self._consume()
            right = self._power()
            if op == "*":
                val *= right
            else:
                if right == 0:
                    raise FormulaError("Division by zero in formula")
                val /= right
        return val

    def _power(self) -> float:
        val = self._factor()
        if self._peek() == "**":
            self._consume()
            # Exponentiation is right-associative
            right = self._power()
            val = val ** right
        return val

    def _factor(self) -> float:
        tok = self._peek()
        if tok == "+":
            self._consume()
            return self._factor()
        elif tok == "-":
            self._consume()
            return -self._factor()
        return self._atom()

    def _atom(self) -> float:
        tok = self._consume()
        if tok == "(":
            val = self._expr()
            closing = self._consume()
            if closing != ")":
                raise FormulaError(f"Expected ')', got '{closing}'")
            return val

        # Dice atom, rolled now
        dice = _DICE_RE.match(tok)
        if dice:
            count, sides = int(dice.group(1)), int(dice.group(2))
            if sides < 1:
                raise FormulaError(f"Invalid dice in formula: '{tok}'")
            return float(sum(self.rng.randint(1, sides) for _ in range(count)))

        # Number literal
        try:
            return float(tok)
        except ValueError:
            pass

        if tok in ("(", ")", "+", "-", "*", "/", "**"):
            raise FormulaError(f"Unexpected token '{tok}'")

        # Variable lookup
        if tok in self.variables:
            return float(self.variables[tok])
        if tok.lower() in self.lowered:
            return float(self.lowered[tok.lower()])
        if self.resolver is not None:
            try:
                return float(self.resolver(tok))
            except KeyError:
                pass

        raise FormulaError(f"Unknown variable in formula: '{tok}'")


def evaluate_formula(
    formula: str,
    *,
    resolver: Resolver | None = None,
    rng: random.Random | None = None,
    **kwargs: Any,
) -> float:
    """Safely evaluates a formula string.

    Args:
        formula: The expression, e.g. ``"2d10+INT"``.
        resolver: Optional lookup for names not passed as keyword variables.
            Raise ``KeyError`` for unknown names.
        rng: Random source for dice atoms.
        **kwargs: Named variables (matched case-insensitively).
    """
    cleaned = formula.strip()
    if not cleaned:
        return 0.0
    tokens = _tokenize(cleaned)
    parser = _Parser(tokens, {k: float(v) for k, v in kwargs.items()}, resolver, rng)
    return parser.parse()


def validate_formula(formula: str, known_name: Callable[[str], bool] | None = None) -> str | None:
    """Checks formula syntax without real values. Returns an error message or None.

    Every variable evaluates to 1 and every die rolls 1. ``known_name`` can reject
    variables that would fail at runtime.
    """
    class _Ones(random.Random):
        def randint(self, a: int, b: int) -> int:  # type: ignore[override]
            return 1

    def resolve(name: str) -> float:
        if known_name is not None and not known_name(name):
            raise KeyError(name)
        return 1.0

    try:
        evaluate_formula(formula, resolver=resolve, rng=_Ones())
    except FormulaError as exc:
        if "Division by zero" in str(exc):
            return None
        return str(exc)
    return None

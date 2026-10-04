"""Safe mathematical formula evaluator.

Replaces eval() for formulas like "base_exp * (1.1 ** (level - 1))".
Supports: +, -, *, /, **, unary +/-, parentheses, floating/integer numbers, and variables.
"""
from __future__ import annotations

import re
from typing import Any

_TOKEN_RE = re.compile(r"\s*(?:(\d+\.?\d*)|(\*\*|[+\-*/()])|([a-zA-Z_]\w*))\s*")


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
        token = match.group(1) or match.group(2) or match.group(3)
        tokens.append(token)
        pos = match.end()
    return tokens


class _Parser:
    def __init__(self, tokens: list[str], variables: dict[str, float]):
        self.tokens = tokens
        self.variables = variables
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

        # Number literal
        try:
            return float(tok)
        except ValueError:
            pass

        # Variable lookup
        if tok in self.variables:
            return float(self.variables[tok])
        elif tok.lower() in {k.lower(): v for k, v in self.variables.items()}:
            lookup = {k.lower(): v for k, v in self.variables.items()}
            return float(lookup[tok.lower()])

        raise FormulaError(f"Unknown variable in formula: '{tok}'")


def evaluate_formula(formula: str, **kwargs: Any) -> float:
    """Safely evaluates a formula string with the provided keyword variables."""
    cleaned = formula.strip()
    if not cleaned:
        return 0.0
    tokens = _tokenize(cleaned)
    parser = _Parser(tokens, {k: float(v) for k, v in kwargs.items()})
    return parser.parse()

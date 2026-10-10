"""Tokenizer shared by Action Strings and Attack Script lines.

Parameters are whitespace-free tokens, so splitting on whitespace is the main
rule. Braces always separate. A parenthesis is split off a word only when it is
unbalanced inside that word: ``(WITH_TAG`` becomes ``(`` + ``WITH_TAG``, while
the formula ``(30-20)`` stays one token. A trailing colon is split off (``70:``).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

WORD = "WORD"
LPAREN = "LPAREN"
RPAREN = "RPAREN"
LBRACE = "LBRACE"
RBRACE = "RBRACE"
COLON = "COLON"

_SYMBOLS = {"(": LPAREN, ")": RPAREN, "{": LBRACE, "}": RBRACE, ":": COLON}


@dataclass(frozen=True)
class Token:
    kind: str
    text: str

    @property
    def upper(self) -> str:
        return self.text.upper()

    def is_word(self, *values: str) -> bool:
        return self.kind == WORD and (not values or self.upper in values)


def strip_comment(line: str) -> str:
    return line.split("#", 1)[0].strip()


def tokenize(line: str) -> list[Token]:
    tokens: list[Token] = []
    for raw in strip_comment(line).split():
        for piece in re.split(r"([{}])", raw):
            if not piece:
                continue
            if piece in "{}":
                tokens.append(Token(_SYMBOLS[piece], piece))
            else:
                _split_word(piece, tokens)
    return tokens


def _split_word(word: str, out: list[Token]) -> None:
    while word.startswith("(") and word.count("(") > word.count(")"):
        out.append(Token(LPAREN, "("))
        word = word[1:]
    trailing = 0
    while word.endswith(")") and word.count(")") > word.count("("):
        trailing += 1
        word = word[:-1]
    colon = False
    if len(word) > 1 and word.endswith(":"):
        colon = True
        word = word[:-1]
    if word == ":":
        out.append(Token(COLON, ":"))
    elif word:
        out.append(Token(WORD, word))
    if colon:
        out.append(Token(COLON, ":"))
    out.extend(Token(RPAREN, ")") for _ in range(trailing))

"""Registries for Action DSL commands and target filters.

Adding a verb or filter means decorating one function; the parser learns its
name and arity from here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class CommandSpec:
    name: str
    params: list[str]  # param kinds; a trailing "?" marks optional
    handler: Callable[..., None]

    @property
    def required(self) -> int:
        return sum(1 for p in self.params if not p.endswith("?"))


@dataclass
class FilterSpec:
    name: str
    arity: int
    subject: str  # "character" | "action"
    fn: Callable[[Any, list[str], Any], bool]


COMMANDS: dict[str, CommandSpec] = {}
FILTERS: dict[str, FilterSpec] = {}


def register_command(name: str, params: list[str]) -> Callable:
    def decorator(fn: Callable) -> Callable:
        COMMANDS[name.upper()] = CommandSpec(name.upper(), params, fn)
        return fn
    return decorator


def register_filter(name: str, arity: int, subject: str = "character") -> Callable:
    def decorator(fn: Callable) -> Callable:
        FILTERS[name.upper()] = FilterSpec(name.upper(), arity, subject, fn)
        return fn
    return decorator

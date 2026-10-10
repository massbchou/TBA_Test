"""Queue for DELAY lines.

TURNS delays fire at the start of the caster's N-th subsequent turn; ROUNDS and
TIME_UNITS delays fire when the combat clock reaches their due time.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from src.models.character import Character


@dataclass
class PendingLine:
    caster: "Character"
    fire: Callable[[], None]
    due_turn: int | None = None
    due_clock: float | None = None


class Scheduler:
    def __init__(self) -> None:
        self.pending: list[PendingLine] = []

    def __len__(self) -> int:
        return len(self.pending)

    def after_turns(self, caster: "Character", turns: int, fire: Callable[[], None]) -> None:
        self.pending.append(PendingLine(caster, fire, due_turn=caster.turn_count + turns))

    def at_clock(self, caster: "Character", due: float, fire: Callable[[], None]) -> None:
        self.pending.append(PendingLine(caster, fire, due_clock=due))

    def _pop(self, predicate: Callable[[PendingLine], bool]) -> list[PendingLine]:
        due = [p for p in self.pending if predicate(p)]
        self.pending = [p for p in self.pending if p not in due]
        return due

    def due_for_turn(self, caster: "Character") -> list[PendingLine]:
        return self._pop(lambda p: p.caster is caster and p.due_turn is not None
                         and p.due_turn <= caster.turn_count)

    def due_at_clock(self, clock: float) -> list[PendingLine]:
        due = self._pop(lambda p: p.due_clock is not None and p.due_clock <= clock)
        return sorted(due, key=lambda p: p.due_clock)

    def cancel_for(self, caster: "Character") -> int:
        return len(self._pop(lambda p: p.caster is caster))

    def clear(self) -> None:
        self.pending = []

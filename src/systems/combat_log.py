"""Ordered record of actions taken in a battle (drives LAST_ACTOR / LAST_ACTION)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.character import Character
    from src.systems.actions.definitions import ActionDef


@dataclass
class LogEntry:
    actor: "Character"
    action: "ActionDef"
    targets: list["Character"] = field(default_factory=list)


class CombatLog:
    def __init__(self) -> None:
        self.entries: list[LogEntry] = []

    def record(self, actor: "Character", action: "ActionDef", targets: list["Character"]) -> None:
        self.entries.append(LogEntry(actor, action, list(targets)))

    @property
    def last_actor(self) -> "Character | None":
        return self.entries[-1].actor if self.entries else None

    @property
    def last_action(self) -> "ActionDef | None":
        return self.entries[-1].action if self.entries else None

"""Unified definitions for everything a character can do: techniques, spells,
items and predefined actions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from src.systems.actions.nodes import Diagnostic, Program
from src.systems.actions.parser import parse_program

SOURCE_TECHNIQUE = "technique"
SOURCE_SPELL = "spell"
SOURCE_ITEM = "item"
SOURCE_BASIC = "basic"


@dataclass
class ActionDef:
    id: str
    name: str
    source: str
    description: str = ""
    tags: set[str] = field(default_factory=set)
    costs: dict[str, int] = field(default_factory=dict)
    action_string: str | None = None
    predefined: dict[str, Any] | None = None
    ai_target: str | None = None
    usable_in_combat: bool = True
    program: Program | None = None

    def has_tag(self, tag: str) -> bool:
        return tag.lower() in self.tags

    @classmethod
    def from_data(cls, action_id: str, data: dict[str, Any], source: str) -> "ActionDef":
        tags = {t.lower() for t in data.get("tags", [])}
        tags.add(source)  # implicit source tag, e.g. "spell"
        defn = cls(
            id=action_id,
            name=data.get("name", action_id),
            source=source,
            description=data.get("description", ""),
            tags=tags,
            costs={k.lower(): int(v) for k, v in data.get("costs", {}).items()},
            action_string=data.get("action_string"),
            predefined=data.get("predefined_action"),
            ai_target=data.get("ai_target"),
            usable_in_combat=bool(data.get("usable_in_combat", True)),
        )
        if defn.action_string is not None:
            defn.program = parse_program(defn.action_string, source=f"{source}:{action_id}")
        return defn

    def diagnostics(self) -> list[Diagnostic]:
        from src.systems.actions.predefined import PREDEFINED

        where = f"{self.source}:{self.id}"
        if self.action_string is None and self.predefined is None:
            return [Diagnostic("error", "needs either action_string or predefined_action", source=where)]
        if self.action_string is not None and self.predefined is not None:
            return [Diagnostic("error", "has both action_string and predefined_action", source=where)]
        if self.predefined is not None and self.predefined.get("name") not in PREDEFINED:
            return [Diagnostic("error", f"unknown predefined action {self.predefined.get('name')!r}", source=where)]
        return list(self.program.diagnostics) if self.program else []


class ActionRegistry:
    """All ActionDefs by id. Ids must be unique across every source."""

    def __init__(self) -> None:
        self._defs: dict[str, ActionDef] = {}

    def add(self, defn: ActionDef) -> None:
        if defn.id in self._defs:
            raise ValueError(f"Duplicate action id '{defn.id}' ({defn.source} vs {self._defs[defn.id].source})")
        self._defs[defn.id] = defn

    def get(self, action_id: str) -> ActionDef | None:
        return self._defs.get(action_id)

    def __getitem__(self, action_id: str) -> ActionDef:
        return self._defs[action_id]

    def __contains__(self, action_id: object) -> bool:
        return action_id in self._defs

    def all(self) -> Iterable[ActionDef]:
        return self._defs.values()

    @classmethod
    def build(
        cls,
        abilities: dict[str, Any] | None = None,
        spells: dict[str, Any] | None = None,
        items: dict[str, Any] | None = None,
    ) -> "ActionRegistry":
        from src.systems.actions.predefined import BUILTIN_ACTIONS

        registry = cls()
        for action_id, data in BUILTIN_ACTIONS.items():
            registry.add(ActionDef.from_data(action_id, data, SOURCE_BASIC))
        for source, table in ((SOURCE_TECHNIQUE, abilities), (SOURCE_SPELL, spells), (SOURCE_ITEM, items)):
            for action_id, data in (table or {}).items():
                registry.add(ActionDef.from_data(action_id, data, source))
        return registry

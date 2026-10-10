"""Status effect definitions loaded from data/statuses.json."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

STACKING_MODES = ("refresh", "stack", "ignore")


@dataclass
class StatusDef:
    """Static definition of a status. Behaviour lives in ``hooks``: action strings
    keyed by lifecycle hook (``on_apply``, ``on_turn_start``, ``on_turn_end``,
    ``on_damage_taken``, ``on_expire``), executed with the bearer as SELF."""
    name: str
    description: str = ""
    stacking: str = "refresh"
    tags: list[str] = field(default_factory=list)
    hooks: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_data(cls, name: str, data: dict[str, Any]) -> "StatusDef":
        return cls(
            name=name.upper(),
            description=data.get("description", ""),
            stacking=data.get("stacking", "refresh"),
            tags=[t.lower() for t in data.get("tags", [])],
            hooks=dict(data.get("hooks", {})),
        )

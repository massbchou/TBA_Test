"""Tracks top-level session state for a run."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.models.player import Player

RECENT_FLOORS = 3


@dataclass
class GameState:
    """Top-level session state."""
    player: Player
    settings: dict[str, Any] = field(default_factory=dict)
    current_level: int = 1
    is_game_over: bool = False
    recent_offers: list[list[str]] = field(default_factory=list)  # event ids offered, newest last
    used_once: set[str] = field(default_factory=set)               # once_per_run events already taken
    run_stats: dict[str, Any] = field(default_factory=lambda: {
        "enemies_defeated": 0, "gold_earned": 0, "cause_of_death": None,
    })

    def advance_level(self) -> int:
        """Advances to next floor and returns new level."""
        self.current_level += 1
        return self.current_level

    def check_game_over(self) -> bool:
        """Checks if the game has ended."""
        if not self.player.is_alive():
            self.is_game_over = True
        return self.is_game_over

    def remember_offers(self, event_ids: list[str]) -> None:
        self.recent_offers = (self.recent_offers + [list(event_ids)])[-RECENT_FLOORS:]

    def recently_offered(self) -> set[str]:
        return {event_id for floor in self.recent_offers for event_id in floor}

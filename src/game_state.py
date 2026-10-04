"""Tracks top-level session state for a dungeon run."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.models.player import Player


@dataclass
class GameState:
    """Top-level session state."""
    player: Player
    settings: dict[str, Any] = field(default_factory=dict)
    current_level: int = 1
    is_game_over: bool = False

    def advance_level(self) -> int:
        """Advances to next floor and returns new level."""
        self.current_level += 1
        return self.current_level

    def check_game_over(self) -> bool:
        """Checks if the game has ended."""
        if not self.player.is_alive():
            self.is_game_over = True
        return self.is_game_over

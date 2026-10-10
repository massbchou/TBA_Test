"""Level-up perk drawing and application."""
from __future__ import annotations

import math
import random
import re
from typing import TYPE_CHECKING, Any

from src.io.input_provider import AutoInput, InputProvider
from src.rng import get_rng
from src.systems.effects import apply_effects

if TYPE_CHECKING:
    from src.models.player import Player

_TIER_RE = re.compile(r"^tier(\d+)$")


def tier_for_level(level: int, interval: int) -> int:
    """Tier N covers levels ((N-1)*interval, N*interval], matching boss floors."""
    return max(1, math.ceil(level / max(1, interval)))


class PerkManager:
    def __init__(
        self,
        perks: dict[str, list[dict[str, Any]]],
        settings: dict[str, Any],
        input_provider: InputProvider | None = None,
        rng: random.Random | None = None,
        loader: Any = None,
        narrator=print,
    ):
        self.perks = perks
        self.settings = settings
        self.input = input_provider or AutoInput()
        self.rng = rng or get_rng()
        self.loader = loader
        self.narrator = narrator

    def pool_for_level(self, level: int) -> list[dict[str, Any]]:
        """The highest available tier pool not above the level's tier."""
        interval = self.settings.get("events", {}).get("boss_level_interval", 10)
        tier = tier_for_level(level, interval)
        available = sorted(
            (int(m.group(1)), key) for key in self.perks if (m := _TIER_RE.match(key)) and int(m.group(1)) <= tier
        )
        return list(self.perks[available[-1][1]]) if available else []

    def draw(self, player: "Player", level: int) -> list[dict[str, Any]]:
        from src.systems.events import unmet_requirement

        pool = [
            p for p in self.pool_for_level(level)
            if (p.get("repeatable", True) or p["perk_id"] not in player.perks)
            and unmet_requirement(player, p.get("requires")) is None
        ]
        count = min(int(self.settings.get("player", {}).get("level_up_perk_choices", 3)), len(pool))
        return self.rng.sample(pool, count)

    def offer(self, player: "Player", level: int) -> dict[str, Any] | None:
        """Draws perks, asks the player to pick one, and applies it."""
        options = self.draw(player, level)
        if not options:
            self.narrator("No perks are available for this level.")
            return None
        labels = [f"{p['name']} - {p.get('description', '')}" for p in options]
        chosen = options[self.input.choose(f"Level {level}! Choose a perk:", labels)]
        player.perks.append(chosen["perk_id"])
        from src.data_loader import perk_effects

        for msg in apply_effects(player, perk_effects(chosen), self.loader):
            self.narrator(msg)
        return chosen

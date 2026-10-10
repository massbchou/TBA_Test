"""Shared builders for engine tests."""
from __future__ import annotations

import random
from pathlib import Path
from typing import Any, Sequence

from src.data_loader import DataLoader
from src.io.input_provider import ScriptedInput
from src.models.enemy import Enemy
from src.models.player import Player
from src.models.status import StatusDef
from src.systems.actions.context import ActionResult
from src.systems.actions.definitions import ActionDef
from src.systems.battle import Battle

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_loader() -> DataLoader:
    """A loader over the frozen test content in tests/fixtures, independent of shipped game data."""
    loader = DataLoader(data_dir=FIXTURES / "data", settings_path=FIXTURES / "settings.json")
    loader.load_all()
    return loader


DERIVED = {"max_stamina": "40 + 5 * (con - 10)", "max_mana": "20 + 5 * (int - 10)"}

POISON = StatusDef.from_data("POISON", {
    "stacking": "refresh", "tags": ["debuff"], "hooks": {"on_turn_start": "DAMAGE SELF 4 POISON"},
})


def make_player(name: str = "Hero", **stats: Any) -> Player:
    base = {"max_health": 100, "speed": 125, "str": 10, "dex": 10, "con": 10, "int": 10, "defense": 0}
    base.update(stats)
    return Player(name, stats=base, derived_formulas=dict(DERIVED))


def make_enemy(name: str = "Goblin", tags: Sequence[str] = (), **stats: Any) -> Enemy:
    base = {"max_health": 100, "speed": 100, "str": 10, "defense": 0}
    base.update(stats)
    return Enemy(name, stats=base, tags=list(tags))


def make_battle(
    player: Player,
    enemies: Sequence[Enemy],
    answers: Sequence[int | str] = (),
    seed: int = 0,
    statuses: dict[str, StatusDef] | None = None,
    settings: dict[str, Any] | None = None,
) -> Battle:
    messages: list[str] = []
    battle = Battle(
        player,
        enemies,
        rng=random.Random(seed),
        input_provider=ScriptedInput(answers),
        statuses={"POISON": POISON} if statuses is None else statuses,
        settings=settings or {},
        narrator=messages.append,
    )
    battle.messages = messages  # type: ignore[attr-defined]
    return battle


_ids = iter(range(1, 10**9))


def action(text: str, source: str = "spell", action_id: str | None = None, **extra: Any) -> ActionDef:
    """An ad-hoc action. Each call gets a unique id unless one is given, so modifiers from
    separate calls stack the way separate actions would."""
    action_id = action_id or f"test_action_{next(_ids)}"
    return ActionDef.from_data(action_id, {"name": action_id, "action_string": text, **extra}, source)


def run(battle: Battle, caster, text: str, source: str = "spell", **extra: Any) -> ActionResult:
    return battle.orchestrator.execute(caster, action(text, source, **extra), battle)

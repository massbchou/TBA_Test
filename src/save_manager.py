"""Save and load a run as JSON (one file per character in saves/)."""
from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

from src.game_state import GameState
from src.models.character import Resource, Variable
from src.models.player import Player

SAVE_VERSION = 2
SAVE_DIR = Path("saves")

_PLAYER_FIELDS = (
    "name", "class_name", "stats", "tags", "health", "level", "exp", "exp_to_next_level", "gold",
    "inventory", "abilities", "spells", "perks", "basic_attack", "basic_attack_type", "stat_weights",
    "derived_formulas",
)


def save_path(player_name: str, directory: Path = SAVE_DIR) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "_", player_name.lower()).strip("_") or "hero"
    return directory / f"{slug}.json"


def serialize(state: GameState, rng: random.Random) -> dict[str, Any]:
    p = state.player
    version, internal, gauss = rng.getstate()
    return {
        "version": SAVE_VERSION,
        "floor": state.current_level,
        "recent_offers": state.recent_offers,
        "used_once": sorted(state.used_once),
        "run_stats": state.run_stats,
        "rng_state": [version, list(internal), gauss],
        "player": {
            **{f: getattr(p, f) for f in _PLAYER_FIELDS},
            "resources": {k: [r.current, r.maximum] for k, r in p.resources.items()},
            "variables": {k: v.value for k, v in p.variables.items() if v.timer is None},
        },
    }


def deserialize(data: dict[str, Any], settings: dict[str, Any]) -> tuple[GameState, random.Random]:
    if data.get("version") != SAVE_VERSION:
        raise ValueError(f"Unsupported save version {data.get('version')!r}")
    pdata = data["player"]
    player = Player(**{f: pdata[f] for f in _PLAYER_FIELDS})
    player.resources = {k: Resource(cur, mx) for k, (cur, mx) in pdata["resources"].items()}
    player.variables = {k: Variable(v) for k, v in pdata["variables"].items()}
    state = GameState(
        player=player,
        settings=settings,
        current_level=data["floor"],
        recent_offers=[list(f) for f in data["recent_offers"]],
        used_once=set(data["used_once"]),
        run_stats=dict(data["run_stats"]),
    )
    version, internal, gauss = data["rng_state"]
    rng = random.Random()
    rng.setstate((version, tuple(internal), gauss))
    return state, rng


def save(state: GameState, rng: random.Random, directory: Path = SAVE_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = save_path(state.player.name, directory)
    path.write_text(json.dumps(serialize(state, rng)))
    return path


def load(path: Path, settings: dict[str, Any]) -> tuple[GameState, random.Random]:
    return deserialize(json.loads(Path(path).read_text()), settings)


def list_saves(directory: Path = SAVE_DIR) -> list[tuple[Path, str]]:
    """(path, label) for each readable save, newest first."""
    saves = []
    for path in sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text())
            if data.get("version") != SAVE_VERSION:
                continue  # saves from older versions can't be resumed
            p = data["player"]
            saves.append((path, f"{p['name']} - Level {p['level']} {p['class_name']}, floor {data['floor']}"))
        except (OSError, ValueError, KeyError):
            continue
    return saves


def delete(path: Path) -> None:
    Path(path).unlink(missing_ok=True)

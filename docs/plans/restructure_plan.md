# Restructure & Architecture Revamp Plan

## Goal

Reorganize the repository layout, reconcile the diverged `main` and `feat/game-chassis-robust` branches into a single clean codebase, and revamp the architecture to be production-quality — replacing the Jules-generated prototype scaffolding with a well-structured, correctly wired Python project.

## Current State — Problems Identified

### File & Branch Issues
| Problem | Detail |
|:---|:---|
| **Branch split** | `main` has only design docs + data. The prototype code lives solely on an unmerged remote branch (`feat/game-chassis-robust`). No Python code exists on `main`. |
| **Duplicate data files** | The feat branch created simplified _duplicate_ JSON files (`enemies.json`, `events.json`) alongside the richer originals (`enemies.JSON`, `events.JSON`). The originals are authoritative. The code imports the simplified copies, ignoring the real data. |
| **File extension chaos** | Original data uses `.JSON` (uppercase). Feat branch added `.json` (lowercase). Mixed casing on a case-sensitive FS means both files coexist; on macOS (case-insensitive) they shadow each other unpredictably. |
| **Flat layout** | Design docs, settings, and `main.py` are all at the repo root with no separation. |
| **No package structure** | `src/` has no `__init__.py`. No `pyproject.toml`, no dependency management. |

### Architecture Issues
| Problem | Detail |
|:---|:---|
| **`settings.json` divergence** | `main` uses flat keys (`regular_combat`, `ordeal_combat`). Feat branch restructured to nested `combat`/`events`/`player`. Neither alone is complete — main has data the feat branch dropped, and vice versa. |
| **Enemy constructor crash** | `EventManager` calls `Enemy(**enemy_data)`, but `enemy_data` dicts contain keys like `id` and `tags` that aren't `Enemy.__init__` params. This would crash at runtime. |
| **`eval()` for formulas** | `utils.py` uses `eval()` for the EXP formula. Even with `__builtins__: None`, this is fragile and an anti-pattern. |
| **`EventManager` data expectation mismatch** | It indexes enemy/event data as `{e["id"]: e for e in list}` expecting a list-of-dicts, but the authoritative `enemies.JSON` on main is a dict-of-dicts keyed by slug (e.g. `"goblin": {...}`). |
| **Combat system has no real turn resolution** | Player always goes first, then all enemies. The speed/action-time system from the design doc is unimplemented. |
| **Action system & AI are empty stubs** | `ActionOrchestrator` and `AIController` are placeholder classes that do nothing. |

---

## User Review Required

> [!IMPORTANT]
> **Scope Boundary**: This plan covers **Goal 1 (restructure)** and **Goal 2 (architecture revamp)** only. Systems that remain stubs (Action DSL parser, AI scripting engine, shop, items) will be catalogued as extension points in Goal 3 separately — they will *not* be implemented here, but their interfaces and integration points will be cleanly defined so they're ready to build.

> [!IMPORTANT]
> **Branch Strategy**: I propose working directly on `main`. The feat branch code will be cherry-picked and rewritten as needed — we are *not* merging it wholesale. The simplified duplicate data files from the feat branch (`Data/enemies.json`, `Data/events.json`) will be discarded in favor of the richer originals.

---

## Open Questions

> [!IMPORTANT]
> **Save file location**: The design doc mentions saving to JSON. Should save files go into a `saves/` directory at the repo root (gitignored), or do you have a preference?

> [!IMPORTANT]
> **Python version target**: The `.gitignore` and project suggest modern Python. I'll target **Python 3.10+** (for `match` statements and `|` union types) unless you want broader compatibility.

---

## Proposed Changes

### Overview — New Directory Layout

```
TBA_Test/
├── pyproject.toml              # Project metadata & dependencies
├── README.md                   # Updated with setup/run instructions
├── settings.json               # Unified game configuration (reconciled)
│
├── docs/                       # Design documentation (moved from root)
│   ├── GameDesignDoc.md
│   ├── ActionSystem.md
│   └── AttackScriptDesignDocument.md
│
├── data/                       # Game data (renamed from Data/, lowercase)
│   ├── abilities.json          # Renamed from .JSON
│   ├── enemies.json            # Authoritative version (was enemies.JSON)
│   ├── events.json             # Authoritative version (was events.JSON)
│   ├── spells.json             # Renamed from .JSON
│   ├── starting_options.json   # Renamed from .JSON
│   └── level_up_perks.json     # Renamed from .JSON
│
├── saves/                      # Save game directory (gitignored)
│   └── .gitkeep
│
├── src/                        # Game engine package
│   ├── __init__.py
│   │
│   ├── models/                 # Data models (pure state, no logic)
│   │   ├── __init__.py
│   │   ├── character.py        # Base Character dataclass
│   │   ├── player.py           # Player (extends Character)
│   │   └── enemy.py            # Enemy (extends Character)
│   │
│   ├── systems/                # Game systems (logic operating on models)
│   │   ├── __init__.py
│   │   ├── combat.py           # Combat loop with speed-based turn order
│   │   ├── event_manager.py    # Event generation & selection
│   │   ├── events.py           # Event type classes (Combat, Occurrence, Rest)
│   │   ├── action_orchestrator.py  # Action DSL interface (stub w/ clean API)
│   │   └── ai_controller.py    # Enemy AI interface (stub w/ clean API)
│   │
│   ├── data_loader.py          # Centralized data loading & validation
│   ├── formula.py              # Safe formula evaluator (replaces eval())
│   ├── game_state.py           # Top-level session state
│   └── utils.py                # Weighted choice, dice rolling, misc helpers
│
├── main.py                     # Entry point
│
└── tests/                      # Test directory
    ├── __init__.py
    ├── test_formula.py
    ├── test_utils.py
    ├── test_data_loader.py
    └── test_combat_turn_order.py
```

---

### Component 1: Project Setup & File Reorganization

This is the physical restructuring — moving files, normalizing names, adding packaging.

#### [NEW] `pyproject.toml`
Minimal project config. No external dependencies for the core game (stdlib only). Dev dependencies for testing.

```toml
[project]
name = "project-roguelike"
version = "0.1.0"
requires-python = ">=3.10"
description = "A data-driven text-based roguelike adventure"

[project.optional-dependencies]
dev = ["pytest>=7.0"]

[project.scripts]
roguelike = "main:main"
```

#### [MODIFY] `.gitignore`
Add `saves/` directory.

```diff
+ # Game saves
+ saves/
+ !saves/.gitkeep
```

#### [DELETE] `Data/` (entire directory)
Replaced by `data/` with lowercase filenames.

#### [NEW] `data/*.json`
Same content as the current `Data/*.JSON` files, just renamed for consistency. The feat branch's simplified duplicates (`Data/enemies.json`, `Data/events.json`) are **discarded** — the originals from `main` are the canonical versions.

#### [MOVE] Design docs → `docs/`
- `GameDesignDoc.md` → `docs/GameDesignDoc.md`
- `ActionSystem.md` → `docs/ActionSystem.md`
- `AttackScriptDesignDocument.md` → `docs/AttackScriptDesignDocument.md`

#### [NEW] `saves/.gitkeep`
Empty file to preserve the directory in git.

---

### Component 2: Unified `settings.json`

Reconcile the two diverged versions. Keep the feat branch's cleaner nested structure, but restore the data and naming from main's version.

#### [MODIFY] `settings.json`

```json
{
  "player": {
    "exp_formula": "base_exp * (1.1 ** (level - 1))",
    "exp_base": 100,
    "level_up_perk_choices": 3
  },
  "events": {
    "next_event_choices": 2,
    "mystery_choices": 1,
    "boss_level_interval": 10,
    "distributions": {
      "regular": {
        "regular_combat": 45,
        "ordeal_combat": 15,
        "normal_occurrence": 25,
        "reward_occurrence": 10,
        "rest_stop": 5
      },
      "mystery": {
        "regular_combat": 45,
        "ordeal_combat": 15,
        "normal_occurrence": 25,
        "reward_occurrence": 10,
        "rest_stop": 5
      }
    }
  },
  "combat": {
    "round_time_units": 12500,
    "rules_by_level_range": [
      {
        "min_level": 1, "max_level": 5,
        "regular_combat": {
          "enemy_count_weights": { "1": 100 }
        },
        "ordeal_combat": {
          "random_ordeal_weight": 60,
          "preconstructed_ordeal_weight": 40,
          "random_composition": {
            "elite_count_weights": { "1": 100 },
            "normal_count_weights": { "0": 50, "1": 50 }
          }
        }
      },
      {
        "min_level": 6, "max_level": 15,
        "regular_combat": {
          "enemy_count_weights": { "1": 66, "2": 34 }
        },
        "ordeal_combat": {
          "random_ordeal_weight": 60,
          "preconstructed_ordeal_weight": 40,
          "random_composition": {
            "elite_count_weights": { "1": 100 },
            "normal_count_weights": { "0": 20, "1": 50, "2": 30 }
          }
        }
      }
    ]
  }
}
```

Key reconciliation decisions:
- `round_time_units` restored to `12500` (main's value; the feat branch used `125` which contradicts the design doc's "125 time units per round conceptual block" vs "12500 total").
- EXP formula kept as a string, but evaluated by the new safe `formula.py` instead of `eval()`.
- Level-range rules kept as an array (easier to iterate and extend) vs the feat branch's string-keyed dict (`"1-5":`).

---

### Component 3: Data Models (`src/models/`)

Rewrite the character hierarchy using dataclasses for clarity. Fix the constructor mismatches.

#### [NEW] `src/models/character.py`
```python
from dataclasses import dataclass, field

@dataclass
class Character:
    """Base class for all characters (players and enemies)."""
    name: str
    stats: dict[str, int | float] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    health: int = 0
    action_time: int = 0
    status_effects: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if self.health == 0:
            self.health = self.get_stat("max_health")

    def get_stat(self, name: str) -> int | float:
        """Get a stat value, accounting for active buffs/debuffs."""
        base = self.stats.get(name, 0)
        # TODO: Layer in status effect modifications
        return base

    def is_alive(self) -> bool:
        return self.health > 0

    def take_damage(self, amount: int) -> int:
        """Apply damage after defense. Returns actual damage dealt."""
        defense = self.get_stat("defense")
        actual = max(0, amount - defense)
        self.health = max(0, self.health - actual)
        return actual

    def heal(self, amount: int) -> int:
        """Heal up to max_health. Returns actual amount healed."""
        max_hp = self.get_stat("max_health")
        before = self.health
        self.health = min(max_hp, self.health + amount)
        return self.health - before
```

#### [NEW] `src/models/player.py`
```python
from dataclasses import dataclass, field
from src.models.character import Character

@dataclass
class Player(Character):
    """The player character."""
    level: int = 1
    exp: int = 0
    gold: int = 0
    inventory: list = field(default_factory=list)
    abilities: list[str] = field(default_factory=list)
    spells: list[str] = field(default_factory=list)
    exp_to_next_level: int = 0
```

#### [NEW] `src/models/enemy.py`
```python
from dataclasses import dataclass, field
from src.models.character import Character

@dataclass
class Enemy(Character):
    """An enemy character, constructed from data."""
    enemy_id: str = ""
    category: str = "Normal"   # Normal | Elite | Boss | Special
    level: int = 1
    abilities: list[dict] = field(default_factory=list)
    loot_table: list[dict] = field(default_factory=list)
    attack_scripts: list[dict] = field(default_factory=list)
    ai_state: dict = field(default_factory=lambda: {
        "current_script": None,
        "script_line": 0,
        "locked": False,
    })
```

> [!TIP]
> Using dataclasses eliminates the `Enemy(**enemy_data)` crash. We'll build enemies through a factory function in `data_loader.py` that maps the JSON keys to the correct fields, rather than relying on `**kwargs` matching constructor params exactly.

---

### Component 4: Safe Formula Evaluator (`src/formula.py`)

Replace `eval()` with a simple recursive-descent parser that only supports arithmetic.

#### [NEW] `src/formula.py`

Supports: `+`, `-`, `*`, `/`, `**`, parentheses, integer/float literals, and named variables.

```python
"""
Safe arithmetic expression evaluator.

Replaces eval() for formulas like "base_exp * (1.1 ** (level - 1))".
Only supports: +, -, *, /, **, parentheses, numbers, and named variables.
"""
import re
from typing import Any

_TOKEN_RE = re.compile(
    r"\s*(?:(\d+\.?\d*)|(\*\*|[+\-*/()])|([a-zA-Z_]\w*))\s*"
)

def evaluate(expression: str, **variables: float) -> float:
    tokens = _tokenize(expression)
    pos, result = _parse_expr(tokens, 0, variables)
    return result

# ... (tokenizer and recursive descent parser implementation)
```

This will be a small (~80 line) self-contained module with full test coverage.

---

### Component 5: Data Loader (`src/data_loader.py`)

A centralized module that loads all JSON, validates it, and constructs model objects. This replaces the scattered `load_data()` calls and fixes the `Enemy(**data)` constructor mismatch.

#### [NEW] `src/data_loader.py`

```python
"""Loads and validates all game data from JSON files."""
import json
from pathlib import Path
from src.models.enemy import Enemy
from src.models.player import Player

class DataLoader:
    """Loads game data from the data/ directory."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.settings: dict = {}
        self.enemies: dict[str, dict] = {}
        self.abilities: dict[str, dict] = {}
        self.spells: dict[str, dict] = {}
        self.events: dict = {}
        self.starting_options: dict[str, dict] = {}
        self.level_up_perks: dict[str, list] = {}

    def load_all(self) -> None:
        """Load all data files."""
        self.settings = self._load_json("../settings.json")
        self.enemies = self._load_json("enemies.json")
        self.abilities = self._load_json("abilities.json")
        self.spells = self._load_json("spells.json")
        self.events = self._load_json("events.json")
        self.starting_options = self._load_json("starting_options.json")
        self.level_up_perks = self._load_json("level_up_perks.json")

    def build_enemy(self, enemy_slug: str) -> Enemy:
        """Factory: construct an Enemy model from a data slug."""
        data = self.enemies[enemy_slug]
        return Enemy(
            name=data["name"],
            stats=dict(data["stats"]),
            tags=list(data.get("tags", [])),
            enemy_id=enemy_slug,
            category=data.get("category", "Normal"),
            level=data.get("level", 1),
            abilities=list(data.get("abilities", [])),
            loot_table=list(data.get("loot_table", [])),
        )

    def build_player(self, class_name: str) -> Player:
        """Factory: construct a Player from a starting class."""
        data = self.starting_options[class_name]
        return Player(
            name=class_name,
            stats=dict(data["stats"]),
            level=data.get("level", 1),
        )

    def _load_json(self, filename: str) -> dict | list:
        path = self.data_dir / filename
        with open(path) as f:
            return json.load(f)
```

---

### Component 6: Game Systems Revamp (`src/systems/`)

#### [MODIFY] `src/systems/combat.py` — Speed-Based Turn Order

The current combat has a simple "player, then all enemies" loop. The design doc specifies a continuous-time system. This revamp implements it:

```python
class Combat:
    """Manages a single combat encounter with speed-based turn order."""

    def __init__(self, player, settings, data_loader):
        self.player = player
        self.round_time = settings["combat"]["round_time_units"]
        self.data_loader = data_loader

    def run(self, enemies: list["Enemy"]) -> bool:
        """Run combat to completion. Returns True on victory."""
        participants = [self.player] + enemies

        # Reset action timers
        for p in participants:
            p.action_time = 0

        while self.player.is_alive() and any(e.is_alive() for e in enemies):
            # Next actor = lowest action_time among living participants
            living = [p for p in participants if p.is_alive()]
            actor = min(living, key=lambda p: p.action_time)

            if actor is self.player:
                self._player_turn(actor, enemies)
            else:
                self._enemy_turn(actor)

            # Advance action timer: cost = round_time / speed
            speed = max(1, actor.get_stat("speed"))
            actor.action_time += self.round_time // speed

        return self.player.is_alive()
```

This correctly implements the design doc's vision: a character with Speed 125 acts ~once per round (cost = 12500/125 = 100 time units), a character with Speed 250 acts twice as often.

#### [MODIFY] `src/systems/event_manager.py` — Fix Data Format Handling

Rewritten to work with the authoritative dict-of-dicts format from `data/enemies.json` and use `DataLoader.build_enemy()` instead of `Enemy(**data)`.

#### [NEW] `src/systems/action_orchestrator.py` — Clean Stub Interface

```python
class ActionOrchestrator:
    """
    Executes ability/spell effects via Action Strings or Predefined Actions.

    EXTENSION POINT: Implement the Lexer → Parser → Resolver → Executor
    pipeline described in docs/ActionSystem.md.
    """
    def execute(self, caster, action_data: dict, targets: list,
                combat_context: "Combat") -> dict:
        """
        Execute an action.

        Args:
            caster: The Character performing the action.
            action_data: The ability/spell dict from data (must contain
                         either 'action_string' or 'predefined_action').
            targets: Resolved target list.
            combat_context: The current Combat instance for state queries.

        Returns:
            A result dict with keys like 'damage_dealt', 'targets_hit', etc.
        """
        # STUB: Currently performs a simple strength-based attack
        ...
```

#### [NEW] `src/systems/ai_controller.py` — Clean Stub Interface

```python
class AIController:
    """
    Determines enemy actions from their Attack Scripts.

    EXTENSION POINT: Implement the script parser described in
    docs/AttackScriptDesignDocument.md.
    """
    def decide_action(self, enemy, combat_context: "Combat") -> dict | None:
        """
        Evaluate the enemy's attack scripts and return the chosen action.

        Returns:
            A dict like {"ability_id": "fireball"}, or None for default behavior.
        """
        # STUB: Pick the first non-cooldown ability
        ...
```

---

### Component 7: Entry Point & Game State

#### [MODIFY] `main.py`

Rewritten to use `DataLoader`, present character creation, and wire up all systems.

```python
from src.data_loader import DataLoader
from src.game_state import GameState
from src.systems.combat import Combat
from src.systems.event_manager import EventManager

def main():
    # Load all data
    loader = DataLoader()
    loader.load_all()

    # Character creation
    player = character_select(loader)
    state = GameState(player=player, settings=loader.settings)
    combat = Combat(player, loader.settings, loader)
    event_mgr = EventManager(loader)

    # Main loop
    while not state.is_game_over:
        events = event_mgr.generate_choices(state)
        chosen = present_choices(events)
        result = chosen.execute(state, combat)
        if not result:
            break
        state.advance_level()

    print("Game Over.")
```

#### [MODIFY] `src/game_state.py`

```python
from dataclasses import dataclass, field

@dataclass
class GameState:
    """Top-level session state."""
    player: "Player"
    settings: dict
    current_level: int = 1
    is_game_over: bool = False

    def advance_level(self):
        self.current_level += 1

    def check_game_over(self) -> bool:
        if not self.player.is_alive():
            self.is_game_over = True
        return self.is_game_over
```

---

### Component 8: Tests

#### [NEW] `tests/test_formula.py`
Validates the safe expression evaluator with cases like:
- `evaluate("100 * (1.1 ** (level - 1))", level=5)` ≈ 146.41
- Rejects dangerous strings (`__import__`, `os.system`, etc.)

#### [NEW] `tests/test_utils.py`
- `weighted_choice` distribution correctness
- Edge cases (empty dict, zero weights)

#### [NEW] `tests/test_data_loader.py`
- Loads all data files successfully
- `build_enemy("goblin")` returns an `Enemy` with correct stats
- `build_player("Warrior")` returns a `Player` with correct stats

#### [NEW] `tests/test_combat_turn_order.py`
- Character with Speed 250 acts twice before one with Speed 125
- Dead characters are skipped
- Combat ends when all enemies are dead

---

## Extension Points Catalogue

These are the systems that remain as stubs after this restructuring. Each will need its own implementation plan (Goal 3):

| System | Current State | Interface Defined | Location |
|:---|:---|:---|:---|
| **Action String DSL** (Lexer/Parser/Executor) | Empty stub | ✅ `ActionOrchestrator.execute()` | `src/systems/action_orchestrator.py` |
| **Enemy AI Scripting** | Empty stub | ✅ `AIController.decide_action()` | `src/systems/ai_controller.py` |
| **Occurrence Event Logic** | Prints placeholder text | Partial — needs choice resolution engine | `src/systems/events.py` |
| **Shop System** | Not started | ❌ | Needs new module |
| **Inventory & Items** | Player has `inventory: list` only | ❌ | Needs item model + use system |
| **Save/Load** | Not started | ❌ | `src/save_manager.py` |
| **Level-Up Perk Selection** | Data exists, no selection UI | ❌ | Needs perk application logic |
| **Loot Processing** | Data on enemies, no drop logic | ❌ | Goes in `combat.py` post-victory |
| **Status Effects** | `status_effects: list` exists, never processed | ❌ | Needs tick/expire system |
| **Difficulty Scaling** | Design doc TODO | ❌ | Settings + EventManager |

---

## Verification Plan

### Automated Tests
```bash
# From repo root
python -m pytest tests/ -v
```

Expected: All 4 test files pass (formula, utils, data_loader, combat turn order).

### Manual Verification

1. **Run the game**:
   ```bash
   python main.py
   ```
   Should: present class selection → generate floor events → let player pick a path → resolve combat with speed-based turn order → loop until floor 10 prototype cap or death.

2. **Data integrity check**: Confirm all 6 JSON data files load without error and that enemy/player construction produces objects with correct stat values.

3. **File layout audit**: Verify the directory tree matches the proposed layout — no stray files at root, no duplicate data files, no uppercase `.JSON` extensions.

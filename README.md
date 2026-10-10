# TextRogue

A data-driven, turn-based text adventure roguelike RPG engine built in Python.

The current content is **The Lantern Road**: a lone traveller walks west ahead of the Dusk, ten stretches
of road to the gate at Ashgate. Four classes (Warrior, Martial Artist, Priest, Mage), a camp between
floors, waystation shops, and saves. See [docs/world.md](docs/world.md).

## Quick Start

Requires Python 3.10+.

```bash
# Run the game
python3 main.py

# Reproducible / unattended runs
python3 main.py --seed 42          # same seed, same run
python3 main.py --auto --seed 1    # always picks the first option (demo / smoke test)

# Run test suite
python3 -m unittest discover -s tests -v
# or with pytest:
pytest tests/ -v
```

## Directory Structure

```
textrogue/
├── pyproject.toml              # Project configuration and metadata
├── settings.json               # Balance, odds, formulas, and combat rules
├── README.md                   # This documentation
│
├── docs/                       # Technical specifications & design docs
│   ├── game_design.md          # Core game loop, stats, progression
│   ├── action_system.md        # Custom Action String DSL specification
│   └── ai_scripts.md           # Enemy AI scripting state machine
│
├── data/                       # Authoritative JSON content dictionaries
│   ├── abilities.json          # Physical techniques and stamina abilities
│   ├── enemies.json            # Enemy archetypes, stats, loot tables, attack scripts
│   ├── events.json             # Occurrences, ordeals, boss encounters
│   ├── items.json              # Consumable items (action strings)
│   ├── level_up_perks.json     # Tiered level-up bonuses
│   ├── spells.json             # Magical mana spells
│   ├── starting_classes.json   # Starting classes, kits and starting items
│   └── statuses.json           # Status effects and their hooks
│
├── saves/                      # Local game saves (gitignored)
│
├── src/                        # Core game engine
│   ├── models/                 # Data models (Character, Player, Enemy, StatusDef)
│   ├── io/                     # InputProvider: console, scripted (tests), auto
│   ├── systems/                # Game logic systems
│   │   ├── actions/            # Action DSL: lexer, parser, targeting, commands, delays
│   │   ├── ai/                 # Attack Script parser and AI target policies
│   │   ├── action_orchestrator.py # Entry point for executing any action
│   │   ├── ai_controller.py    # Enemy script selection and execution
│   │   ├── battle.py           # Shared combat state: sides, clock, log, status hooks
│   │   ├── combat.py           # Turn loop, player menu, rewards
│   │   ├── effects.py          # Permanent effects for occurrences and perks
│   │   ├── perks.py            # Level-up perk drawing
│   │   ├── event_manager.py    # Procedural floor path generator
│   │   └── events.py           # Combat, Occurrence, and Rest events
│   ├── data_loader.py          # Data loading, model factories, validate()
│   ├── formula.py              # Safe math parser with dice support
│   ├── rng.py                  # Shared seedable RNG
│   ├── stats.py                # Canonical stat names and DSL aliases
│   ├── game_state.py           # Run session state
│   └── utils.py                # Dice rolling, weighted random selection
│
└── tests/                      # Unit test suite
```

## Adding Content

Content is data-only. After editing JSON, run the test suite: `tests/test_data_integrity.py`
fails on any parse error, dangling reference, or unknown effect type.

| To add… | Edit | Notes |
|:---|:---|:---|
| Technique / spell | `data/abilities.json` / `data/spells.json` | `action_string` per [docs/action_system.md](docs/action_system.md); `costs` in stamina/mana; optional `message` (narrated on use, `{caster}` placeholder), `usable_outside_combat` (castable at camp), tag `stacks` (repeat buffs stack instead of refreshing) |
| Item | `data/items.json` | `action_string`, `usable_in_combat`, `usable_outside_combat`, `price`; tag `shop` to appear in waystation shops (`settings.events.shop.always` guarantees stock) |
| Status effect | `data/statuses.json` | `stacking` + `hooks` (action strings run with the bearer as `SELF`); tag `buff` or `debuff` |
| Class | `data/starting_classes.json` | `stats` with `base_hp` (Max HP = `base_hp + 6 × CON`), `stat_weights` (level-up point bias), `basic_attack` + `basic_attack_type`, optional `derived_stats` override (e.g. mana from WIS), kit and `starting_items` |
| Enemy | `data/enemies.json` | `level` is the **base level** for its `stats`; optional `growth` (faster per-level scaling for chosen stats); band tags `early`/`mid`/`late` pick the floors it appears on; `intro` line; weaknesses as negative `<type>_resistance`; `attack_scripts` per [docs/ai_scripts.md](docs/ai_scripts.md). Spawn levels: `levels` on events, `enemy_levels` / `level_range` on floor bands, otherwise the floor ±1 |
| Occurrence | `data/events.json` | Choices hold `effects`, nested `choices`, or `chance` with `success`/`failure`; gate with `requires` (`gold`, `class`, `item`, `stat`, `level`); effect types include `combat` (start a fight, optional `levels`), `exp` (amount may use `floor`, e.g. `"10 + 6 * floor"`) and `learn_action`; `min_level`, `once_per_run` |
| Perk | `data/level_up_perks.json` | `tierN` pools; `effect` or `effects`; `repeatable: false` for one-time perks; `requires` to limit by class |

To add a new *kind* of mechanic, register one handler:

| New… | Register with | In |
|:---|:---|:---|
| Command verb | `@register_command("NAME", params)` | `src/systems/actions/commands.py` |
| Target filter | `@register_filter("NAME", arity)` | `src/systems/actions/filters.py` |
| Predefined action | `@register_predefined("name")` | `src/systems/actions/predefined.py` |
| Occurrence/perk effect | `@register_effect("name", required)` | `src/systems/effects.py` |
| AI target policy | `@register_policy("name")` | `src/systems/ai/policy.py` |


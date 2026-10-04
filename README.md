# Project Roguelike (TBA_Test)

A data-driven, turn-based text adventure RPG built in Python.

## Quick Start

Requires Python 3.10+.

```bash
# Run the game
python3 main.py

# Run test suite
python3 -m unittest discover -s tests -v
# or with pytest:
pytest tests/ -v
```

## Directory Structure

```
TBA_Test/
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
│   ├── enemies.json            # Enemy archetypes, stats, loot tables
│   ├── events.json             # Occurrences, ordeals, boss encounters
│   ├── level_up_perks.json     # Tiered level-up bonuses
│   ├── spells.json             # Magical mana spells
│   └── starting_classes.json   # Starting classes (Warrior, Rogue)
│
├── saves/                      # Local game saves (gitignored)
│
├── src/                        # Core game engine
│   ├── models/                 # Pure data models (Character, Player, Enemy)
│   ├── systems/                # Game logic systems
│   │   ├── combat.py           # Speed-based continuous-time combat engine
│   │   ├── event_manager.py    # Procedural floor path generator
│   │   ├── events.py           # Combat, Occurrence, and Rest events
│   │   ├── action_orchestrator.py # Action DSL orchestrator interface
│   │   └── ai_controller.py    # Enemy AI script controller interface
│   ├── data_loader.py          # Centralized data loader & model factories
│   ├── formula.py              # Safe recursive-descent math parser
│   ├── game_state.py           # Run session state
│   └── utils.py                # Dice rolling, weighted random selection
│
└── tests/                      # Unit test suite
```

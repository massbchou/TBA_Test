"""Main game entry point for TextRogue."""
from __future__ import annotations

import sys
from src.data_loader import DataLoader
from src.game_state import GameState
from src.systems.combat import Combat
from src.systems.event_manager import EventManager


def select_starting_class(loader: DataLoader, default_class: str = "Warrior") -> str:
    """Displays starting classes and selects one."""
    print("Available Starting Classes:")
    options = list(loader.starting_classes.keys())
    for i, opt in enumerate(options, start=1):
        info = loader.starting_classes[opt]
        desc = info.get("description", "")
        print(f"  [{i}] {opt} - {desc}")

    # For automated execution or non-interactive shells, default to first class
    chosen = options[0] if options else default_class
    print(f"\nChosen class: {chosen}")
    return chosen


def main() -> None:
    """Main game loop."""
    print("=" * 60)
    print("                    WELCOME TO TEXTROGUE                    ")
    print("=" * 60)

    # 1. Load game configuration and content
    loader = DataLoader(data_dir="data", settings_path="settings.json")
    loader.load_all()

    # 2. Character creation
    chosen_class = select_starting_class(loader)
    player = loader.build_player(chosen_class, player_name="Adventurer")
    print(f"Player '{player.name}' created! HP: {player.health}/{player.get_stat('max_health')}, Speed: {player.get_stat('speed')}, EXP to Lvl 2: {player.exp_to_next_level}\n")

    # 3. Systems initialization
    game_state = GameState(player=player, settings=loader.settings)
    combat_system = Combat(player=player, settings=loader.settings, data_loader=loader)
    event_manager = EventManager(data_loader=loader)

    # 4. Main floor progression loop
    max_prototype_floor = 10

    while not game_state.check_game_over():
        current_floor = game_state.current_level
        print(f"\n------------------------------------------------------------")
        print(f"                   FLOOR {current_floor} / {max_prototype_floor}                    ")
        print(f"  HP: {player.health}/{player.get_stat('max_health')} | Level: {player.level} | Gold: {player.gold} | EXP: {player.exp}/{player.exp_to_next_level}")
        print(f"------------------------------------------------------------")

        # Generate event choices for this floor
        choices = event_manager.generate_choices(game_state)
        if not choices:
            print("The corridor ends in quiet solitude. No paths remain.")
            break

        print("\nYou perceive multiple paths ahead:")
        for idx, event in enumerate(choices, start=1):
            print(f"  {idx}. {event.get_choice_label()}")

        # Execute chosen path (choose the first option by default)
        chosen_event = choices[0]
        print(f"\n>> Venturing down: {chosen_event.get_choice_label()}")

        event_success = chosen_event.execute(game_state, combat_system)
        if not event_success:
            print(f"\nYour journey comes to an end on Floor {current_floor}.")
            break

        if current_floor >= max_prototype_floor:
            print(f"\n*** CONGRATULATIONS! You have conquered Floor {max_prototype_floor} and survived the prototype run! ***")
            break

        game_state.advance_level()

    print("\n" + "=" * 60)
    print("                        GAME OVER                          ")
    print("=" * 60)


if __name__ == "__main__":
    main()

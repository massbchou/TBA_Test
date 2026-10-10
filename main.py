"""Main game entry point for TextRogue."""
from __future__ import annotations

import argparse
import logging

from src import rng as game_rng
from src.data_loader import DataLoader
from src.game_state import GameState
from src.io.input_provider import AutoInput, ConsoleInput, InputProvider
from src.systems.combat import Combat
from src.systems.event_manager import EventManager
from src.systems.perks import PerkManager


def select_starting_class(loader: DataLoader, input_provider: InputProvider) -> str:
    """Displays starting classes and lets the player pick one."""
    options = list(loader.starting_classes.keys())
    labels = [f"{opt} - {loader.starting_classes[opt].get('description', '')}" for opt in options]
    chosen = options[input_provider.choose("Choose your starting class:", labels)]
    print(f"\nChosen class: {chosen}")
    return chosen


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TextRogue: a data-driven text roguelike.")
    parser.add_argument("--seed", type=int, default=None, help="Seed the RNG for a reproducible run.")
    parser.add_argument("--auto", action="store_true", help="Play unattended, always choosing the first option.")
    parser.add_argument("--floors", type=int, default=10, help="Floor to stop at (prototype cap).")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Main game loop."""
    args = parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    game_rng.seed(args.seed)
    rng = game_rng.get_rng()
    input_provider: InputProvider = AutoInput() if args.auto else ConsoleInput()

    print("=" * 60)
    print("                    WELCOME TO TEXTROGUE                    ")
    print("=" * 60)

    # 1. Load game configuration and content
    loader = DataLoader(data_dir="data", settings_path="settings.json")
    loader.load_all()
    for diag in loader.validate():
        if diag.severity != "info":
            logging.getLogger("textrogue.data").warning("%s", diag)

    # 2. Character creation
    chosen_class = select_starting_class(loader, input_provider)
    player = loader.build_player(chosen_class, player_name="Adventurer")
    print(f"Player '{player.name}' created! HP: {player.health}/{player.get_stat('max_health')}, Speed: {player.get_stat('speed')}, EXP to Lvl 2: {player.exp_to_next_level}\n")

    # 3. Systems initialization
    game_state = GameState(player=player, settings=loader.settings)
    perk_manager = PerkManager(loader.level_up_perks, loader.settings, input_provider, rng, loader)
    combat_system = Combat(
        player=player,
        settings=loader.settings,
        data_loader=loader,
        input_provider=input_provider,
        rng=rng,
        perk_manager=perk_manager,
    )
    event_manager = EventManager(data_loader=loader, rng=rng)

    # 4. Main floor progression loop
    max_prototype_floor = args.floors

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

        labels = [event.get_choice_label() for event in choices]
        chosen_event = choices[input_provider.choose("You perceive multiple paths ahead:", labels)]
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

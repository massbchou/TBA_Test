"""Main game entry point for TextRogue."""
from __future__ import annotations

import argparse
import logging

from pathlib import Path

from src import rng as game_rng
from src import save_manager
from src.data_loader import DataLoader
from src.game_state import GameState
from src.io.input_provider import AutoInput, ConsoleInput, InputProvider
from src.systems.camp import QUIT, Camp
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


def print_run_summary(state: GameState, outcome: str, loader: DataLoader) -> None:
    p = state.player
    stats = state.run_stats
    print("\n" + "-" * 60)
    print(f"  {p.name} the {p.class_name} - {'cleared the road' if outcome == 'cleared' else 'fell on floor ' + str(state.current_level)}")
    if stats.get("cause_of_death") and outcome == "dead":
        print(f"  Slain by: {stats['cause_of_death']}")
    print(f"  Level {p.level} | Enemies defeated: {stats.get('enemies_defeated', 0)} | Gold earned: {stats.get('gold_earned', 0)}")
    if p.perks:
        print(f"  Perks: {', '.join(loader.perk_name(pid) for pid in p.perks)}")
    print("-" * 60)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TextRogue: a data-driven text roguelike.")
    parser.add_argument("--seed", type=int, default=None, help="Seed the RNG for a reproducible run.")
    parser.add_argument("--auto", action="store_true", help="Play unattended, always choosing the first option.")
    parser.add_argument("--floors", type=int, default=10, help="Floor to stop at (prototype cap).")
    parser.add_argument("--save-dir", default=str(save_manager.SAVE_DIR), help="Directory for save files.")
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

    # 2. New game or continue
    save_dir = Path(args.save_dir)
    game_state: GameState | None = None
    saves = [] if args.auto else save_manager.list_saves(save_dir)
    if saves:
        labels = ["New game"] + [f"Continue: {label}" for _, label in saves]
        pick = input_provider.choose("Welcome back, traveller.", labels)
        if pick > 0:
            game_state, loaded_rng = save_manager.load(saves[pick - 1][0], loader.settings)
            rng.setstate(loaded_rng.getstate())
            print(f"\nThe road remembers you, {game_state.player.name}.")
    if game_state is None:
        chosen_class = select_starting_class(loader, input_provider)
        name = input_provider.ask_text("What is your name, traveller?", "Adventurer")
        player = loader.build_player(chosen_class, player_name=name)
        print(f"{player.name} the {chosen_class} sets out. HP {player.health}/{player.get_stat('max_health')}, Speed {player.get_stat('speed')}.\n")
        game_state = GameState(player=player, settings=loader.settings)
    player = game_state.player

    # 3. Systems initialization
    perk_manager = PerkManager(loader.level_up_perks, loader.settings, input_provider, rng, loader)
    combat_system = Combat(
        player=player,
        settings=loader.settings,
        data_loader=loader,
        input_provider=input_provider,
        rng=rng,
        perk_manager=perk_manager,
        run_stats=game_state.run_stats,
    )
    event_manager = EventManager(data_loader=loader, rng=rng)
    saver = None if args.auto else (lambda state: str(save_manager.save(state, rng, save_dir)))
    camp = Camp(combat_system, save=saver)

    # 4. Main floor progression loop
    max_prototype_floor = args.floors
    outcome = "dead"

    while not game_state.check_game_over():
        current_floor = game_state.current_level
        if current_floor > 1 and camp.visit(game_state) == QUIT:
            outcome = "saved"
            break

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
        if chosen_event.is_mystery:
            chosen_event.is_mystery = False
            print(f"   The fog parts... {chosen_event.get_choice_label()}")

        if current_floor >= max_prototype_floor:
            combat_system.perk_manager = None  # the run ends after this fight; perk choices would be moot
        event_success = chosen_event.execute(game_state, combat_system)
        if not event_success:
            print(f"\nYour journey comes to an end on Floor {current_floor}.")
            break

        if current_floor >= max_prototype_floor:
            print(f"\n*** CONGRATULATIONS! You have conquered Floor {max_prototype_floor} and survived the prototype run! ***")
            outcome = "cleared"
            break

        game_state.advance_level()

    if outcome == "saved":
        print("\nYour lantern is banked for the night. The road will wait.")
        return
    if not args.auto:
        save_manager.delete(save_manager.save_path(player.name, save_dir))  # roguelike: a finished run can't be resumed
    print_run_summary(game_state, outcome, loader)

    print("\n" + "=" * 60)
    print("                         THE END" if outcome == "cleared" else "                        GAME OVER")
    print("=" * 60)


if __name__ == "__main__":
    main()

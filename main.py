from src.game_state import GameState
from src.player import Player
from src.event_manager import EventManager
from src.combat import Combat
from src.action_orchestrator import ActionOrchestrator
from src.utils import load_data

def main():
    """Main game entry point and loop."""
    print("Loading game data...")
    settings = load_data("settings.json")
    enemies_data = load_data("Data/enemies.json")
    events_data = load_data("Data/events.json")

    # Initialize systems
    action_orchestrator = ActionOrchestrator()
    combat_system = Combat(None, settings, action_orchestrator)

    # Create Player and GameState
    # TODO: Implement character creation or loading a saved game
    player_stats = {"max_health": 100, "strength": 10, "max_level": 20}
    player = Player("Hero", player_stats)
    combat_system.player = player # Link player to combat system
    game_state = GameState(player)

    player.calculate_exp_to_next_level(settings["player"]["experience_to_level_formula"])
    print(f"Welcome, {player.name}! You are Level {player.level}.")
    print(f"EXP to next level: {player.experience_to_next_level}")

    # Initialize EventManager with all data
    event_manager = EventManager(settings, events_data, enemies_data)

    # Main game loop
    while not game_state.check_game_over():
        print(f"\n--- Floor {game_state.current_level} ---")

        # 1. Generate event choices
        event_choices = event_manager.get_next_event_choices(game_state)

        if not event_choices:
            print("You wander aimlessly. There are no events to be found here.")
            print("GAME PROTOTYPE END")
            break

        # 2. Present choices to the player
        print("You see several paths ahead:")
        for i, event in enumerate(event_choices):
            print(f"{i + 1}. A path leading towards a '{event.type}' event.")

        # TODO: Implement player input for choice
        # For now, automatically choose the first event
        choice_index = 0
        print(f"\nYou choose path {choice_index + 1}.")

        chosen_event = event_choices[choice_index]

        # 3. Execute the chosen event
        event_result = chosen_event.execute(game_state, combat_system)

        if not event_result:
            # If the event returns False (e.g., player lost combat), end the game.
            break

        # TODO: This is a placeholder for post-event logic like EXP awards
        if chosen_event.type == "Combat":
            player.add_exp(50, settings["player"]["experience_to_level_formula"])

        # 4. Move to the next level
        game_state.next_level()

        # TODO: Add save/exit functionality
        if game_state.current_level > 10: # Temp break condition
            print("\nYou've explored deep into the dungeon. The prototype ends here.")
            break

    print("\n--- Game Over ---")


if __name__ == "__main__":
    main()
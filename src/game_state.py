class GameState:
    """Tracks the current state of the game."""
    def __init__(self, player):
        self.current_level = 1
        self.player = player
        self.is_game_over = False

    def next_level(self):
        self.current_level += 1

    def check_game_over(self):
        if not self.player.is_alive():
            self.is_game_over = True
        return self.is_game_over
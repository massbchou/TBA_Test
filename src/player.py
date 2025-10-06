from src.character import Character
from src.utils import evaluate_formula

class Player(Character):
    """Represents the player character."""
    def __init__(self, name, stats, level=1):
        super().__init__(name, stats)
        self.level = level
        self.exp = 0
        self.gold = 0
        self.inventory = []
        self.experience_to_next_level = 0

    def calculate_exp_to_next_level(self, formula):
        """Calculates the EXP needed for the next level based on a formula."""
        self.experience_to_next_level = int(evaluate_formula(formula, level=self.level))

    def add_exp(self, amount, exp_formula):
        """Adds experience and checks for level up."""
        if self.level >= self.get_stat("max_level"):
            return

        self.exp += amount
        print(f"You gained {amount} EXP.")

        if self.experience_to_next_level == 0:
             self.calculate_exp_to_next_level(exp_formula)

        while self.exp >= self.experience_to_next_level:
            self.exp -= self.experience_to_next_level
            self.level_up(exp_formula)

    def level_up(self, exp_formula):
        """Handles the player leveling up."""
        self.level += 1
        print(f"Congratulations! You've reached Level {self.level}!")
        # TODO: Implement perk/stat choices
        self.calculate_exp_to_next_level(exp_formula)
        print(f"EXP to next level: {self.experience_to_next_level}")
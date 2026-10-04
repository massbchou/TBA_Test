from dataclasses import dataclass, field
from src.models.character import Character
from src.formula import evaluate_formula


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

    def calculate_exp_to_next_level(self, formula: str, base_exp: int = 100) -> None:
        """Calculates EXP needed for next level using safe formula evaluation."""
        self.exp_to_next_level = int(evaluate_formula(formula, base_exp=base_exp, level=self.level))

    def add_exp(self, amount: int, formula: str, base_exp: int = 100) -> list[int]:
        """
        Adds experience and handles potential level-ups.
        Returns a list of levels reached during this award.
        """
        levels_gained: list[int] = []
        if self.level >= int(self.get_stat("max_level") or 999):
            return levels_gained

        self.exp += amount

        if self.exp_to_next_level <= 0:
            self.calculate_exp_to_next_level(formula, base_exp)

        while self.exp >= self.exp_to_next_level and self.exp_to_next_level > 0:
            self.exp -= self.exp_to_next_level
            self.level += 1
            levels_gained.append(self.level)
            self.calculate_exp_to_next_level(formula, base_exp)

        return levels_gained

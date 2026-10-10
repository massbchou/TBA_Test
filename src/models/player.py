from dataclasses import dataclass, field

from src.formula import evaluate_formula
from src.models.character import Character, Resource
from src.stats import canonical_stat, is_known_stat


@dataclass
class Player(Character):
    """The player character."""
    level: int = 1
    exp: int = 0
    gold: int = 0
    inventory: dict[str, int] = field(default_factory=dict)
    abilities: list[str] = field(default_factory=list)
    spells: list[str] = field(default_factory=list)
    perks: list[str] = field(default_factory=list)
    class_name: str = ""
    basic_attack: str = "1.0*STR"
    basic_attack_type: str = "PHYSICAL"
    stat_weights: dict[str, float] = field(default_factory=dict)
    derived_formulas: dict[str, str] = field(default_factory=dict)
    exp_to_next_level: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        self.recalculate_derived()

    # ------------------------------------------------------- derived stats

    def _base_value(self, name: str) -> float:
        if name.lower() == "level":
            return float(self.level)
        key = canonical_stat(name)
        if key in self.stats or is_known_stat(key):
            return float(self.stats.get(key, 0))
        raise KeyError(name)

    def recalculate_derived(self) -> None:
        """Recomputes derived maxima from base stats.

        ``max_health`` (if it has a formula) becomes the formula plus ``hp_bonus``;
        ``max_stamina`` / ``max_mana`` become resource maxima. A raised maximum also
        raises the current value by the difference; a lowered one clamps it.
        """
        for stat, formula in self.derived_formulas.items():
            if not stat.startswith("max_"):
                continue
            new_max = max(0, int(evaluate_formula(formula, resolver=self._base_value)))
            if stat == "max_health":
                new_max = max(1, new_max + int(self.stats.get("hp_bonus", 0)))
                old_max = int(self.stats.get("max_health", 0))
                self.stats["max_health"] = new_max
                self.health = max(0, min(new_max, self.health + max(0, new_max - old_max)))
                continue
            resource = stat[4:]
            res = self.resources.get(resource)
            if res is None:
                self.resources[resource] = Resource(new_max, new_max)
                continue
            gained = new_max - res.maximum
            res.maximum = new_max
            res.current = max(0, min(new_max, res.current + max(0, gained)))

    def _on_base_stats_changed(self) -> None:
        self.recalculate_derived()

    def modify_base_stat(self, name: str, delta: float) -> None:
        """Max HP is derived from CON when it has a formula, so direct Max HP changes
        (perks, events) go to the separate ``hp_bonus`` stat instead."""
        if canonical_stat(name) == "max_health" and "max_health" in self.derived_formulas:
            name = "hp_bonus"
        super().modify_base_stat(name, delta)

    def full_heal(self) -> None:
        self.health = int(self.get_stat("max_health"))
        self.refill_resources()

    def owns(self, action_id: str) -> bool:
        return action_id in self.abilities or action_id in self.spells

    def refill_resources(self) -> None:
        for res in self.resources.values():
            res.current = res.maximum

    # ----------------------------------------------------------- inventory

    def add_item(self, item_id: str, quantity: int = 1) -> None:
        if quantity > 0:
            self.inventory[item_id] = self.inventory.get(item_id, 0) + quantity

    def remove_item(self, item_id: str, quantity: int = 1) -> bool:
        have = self.inventory.get(item_id, 0)
        if have < quantity:
            return False
        if have == quantity:
            del self.inventory[item_id]
        else:
            self.inventory[item_id] = have - quantity
        return True

    # ------------------------------------------------------------ leveling

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

from dataclasses import dataclass, field


@dataclass
class Character:
    """Base class for all characters (players and enemies)."""
    name: str
    stats: dict[str, int | float] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    health: int = 0
    action_time: int = 0
    status_effects: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.health <= 0:
            self.health = int(self.get_stat("max_health"))

    def get_stat(self, name: str) -> int | float:
        """Get a stat value, accounting for active buffs/debuffs."""
        base = self.stats.get(name, 0)
        # TODO: Layer in status effect modifications
        return base

    def is_alive(self) -> bool:
        """Check if character is alive."""
        return self.health > 0

    def take_damage(self, amount: int) -> int:
        """Apply damage after defense. Returns actual damage dealt."""
        defense = int(self.get_stat("defense"))
        actual = max(0, amount - defense)
        self.health = max(0, self.health - actual)
        return actual

    def heal(self, amount: int) -> int:
        """Heal up to max_health. Returns actual amount healed."""
        max_hp = int(self.get_stat("max_health"))
        before = self.health
        self.health = min(max_hp, self.health + amount)
        return self.health - before

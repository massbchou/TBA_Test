class Character:
    """Base class for all characters in the game (Player and Enemies)."""
    def __init__(self, name, stats):
        self.name = name
        self.stats = stats
        self.health = self.get_stat("max_health")
        self.action_time = 0
        self.status_effects = []

    def get_stat(self, stat_name):
        # TODO: Implement modifications from status effects
        return self.stats.get(stat_name, 0)

    def is_alive(self):
        return self.health > 0

    def take_damage(self, amount):
        self.health = max(0, self.health - amount)
        print(f"{self.name} takes {amount} damage.")

    def heal(self, amount):
        max_health = self.get_stat("max_health")
        self.health = min(max_health, self.health + amount)
        print(f"{self.name} heals for {amount}.")
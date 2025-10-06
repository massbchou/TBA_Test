class Combat:
    """Handles the logic for a single combat encounter."""
    def __init__(self, player, settings, action_orchestrator):
        self.player = player
        self.settings = settings
        self.action_orchestrator = action_orchestrator
        self.enemies = []
        self.participants = []

    def run_combat(self, encounter):
        """Main loop for a combat encounter. Returns True on player victory, False on defeat."""
        self.enemies = encounter
        self.participants = [self.player] + self.enemies

        print("--- Combat Starts! ---")
        for enemy in self.enemies:
            print(f"You face: {enemy.name} (HP: {enemy.health})")

        # Main combat loop
        while self.player.is_alive() and any(e.is_alive() for e in self.enemies):
            # TODO: Implement proper turn order based on speed/action_time

            # Player Turn
            if self.player.is_alive():
                self._process_player_turn()

            # Enemy Turns
            for enemy in self.enemies:
                if enemy.is_alive():
                    self._process_enemy_turn(enemy)

            # Check for player defeat mid-round
            if not self.player.is_alive():
                break

        # End of combat
        if self.player.is_alive():
            print("--- Combat Victory! ---")
            # TODO: Process loot and EXP
            return True
        else:
            print("--- You have been defeated. ---")
            return False

    def _process_player_turn(self):
        """Placeholder for player's turn logic."""
        print("\n--- Your Turn ---")
        # TODO: Implement a real action menu (Attack, Defend, Item, etc.)
        # For now, a simple attack on the first living enemy.
        target = next((e for e in self.enemies if e.is_alive()), None)
        if target:
            print(f"You attack {target.name}!")
            # In a real implementation, this would use the Action System.
            damage = self.player.get_stat("strength")
            target.take_damage(damage)
        else:
            print("No targets left.")

    def _process_enemy_turn(self, enemy):
        """Placeholder for an enemy's turn logic."""
        print(f"\n--- {enemy.name}'s Turn ---")
        # TODO: Integrate with AIController to get an action
        # For now, a simple attack on the player.
        print(f"{enemy.name} attacks you!")
        damage = enemy.get_stat("strength")
        self.player.take_damage(damage)
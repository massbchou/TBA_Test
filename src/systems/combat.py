"""Combat system with speed-based continuous-time turn resolution."""
from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from src.models.character import Character
from src.systems.action_orchestrator import ActionOrchestrator
from src.systems.ai_controller import AIController

if TYPE_CHECKING:
    from src.data_loader import DataLoader
    from src.models.enemy import Enemy
    from src.models.player import Player


class Combat:
    """Manages tactical turn-based combat encounters."""

    def __init__(
        self,
        player: Player,
        settings: dict[str, Any],
        data_loader: DataLoader | None = None,
        action_orchestrator: ActionOrchestrator | None = None,
        ai_controller: AIController | None = None,
    ):
        self.player = player
        self.settings = settings
        self.data_loader = data_loader
        self.round_time_units = int(
            self.settings.get("combat", {}).get("round_time_units", 12500)
        )
        self.action_orchestrator = action_orchestrator or ActionOrchestrator(data_loader)
        self.ai_controller = ai_controller or AIController(data_loader)
        self.enemies: list[Enemy] = []

    def run(self, encounter: list[Enemy]) -> bool:
        """
        Executes a combat encounter until player victory or defeat.

        Returns:
            True on victory, False on defeat.
        """
        self.enemies = encounter
        participants: list[Character] = [self.player] + self.enemies

        print("\n================== COMBAT STARTS ==================")
        print(f"Hero: {self.player.name} (HP: {self.player.health}/{self.player.get_stat('max_health')}, Speed: {self.player.get_stat('speed')})")
        for enemy in self.enemies:
            print(f"Enemy: {enemy.name} (HP: {enemy.health}/{enemy.get_stat('max_health')}, Speed: {enemy.get_stat('speed')})")

        # Initialize action timers
        for p in participants:
            p.action_time = 0

        round_counter = 1

        while self.player.is_alive() and any(e.is_alive() for e in self.enemies):
            living = [p for p in participants if p.is_alive()]
            # Actor with lowest action_time takes the turn
            actor = min(living, key=lambda p: p.action_time)

            if actor is self.player:
                self._process_player_turn()
            else:
                self._process_enemy_turn(actor)  # type: ignore[arg-type]

            # Advance actor's action timer based on speed
            speed = max(1, int(actor.get_stat("speed") or 100))
            cost = max(1, self.round_time_units // speed)
            actor.action_time += cost

            round_counter += 1
            if round_counter > 500:
                print("Combat reached maximum rounds safeguard.")
                break

        if self.player.is_alive():
            print("\n>>> VICTORY! All enemies have been defeated! <<<")
            self._process_post_combat_rewards()
            return True
        else:
            print("\n>>> DEFEAT! You have fallen in battle... <<<")
            return False

    def _process_player_turn(self) -> None:
        """Executes a player action against living enemies."""
        living_enemies = [e for e in self.enemies if e.is_alive()]
        if not living_enemies:
            return

        # Target the lowest health enemy
        target = min(living_enemies, key=lambda e: e.health)

        action_data = {
            "name": "Standard Strike",
            "action_string": "DAMAGE 1_ENEMY CHOICE 1.5*STR PHYSICAL",
        }
        res = self.action_orchestrator.execute(
            caster=self.player,
            action_data=action_data,
            targets=[target],
            combat_context=self,
        )

        for eff in res.get("effects", []):
            print(f"  -> You strike {eff['target']} for {eff['amount']} damage! ({target.health}/{target.get_stat('max_health')} HP left)")

    def _process_enemy_turn(self, enemy: Enemy) -> None:
        """Executes an enemy turn via AIController."""
        action = self.ai_controller.decide_action(enemy, self)
        if not action:
            return

        res = self.action_orchestrator.execute(
            caster=enemy,
            action_data=action,
            targets=[self.player],
            combat_context=self,
        )

        for eff in res.get("effects", []):
            if eff.get("type") == "damage":
                print(f"  <- {enemy.name} uses [{action.get('name')}] on you for {eff['amount']} damage! (Your HP: {self.player.health}/{self.player.get_stat('max_health')})")
            elif eff.get("type") == "heal":
                print(f"  <- {enemy.name} heals for {eff['amount']} HP!")

    def _process_post_combat_rewards(self) -> None:
        """Distributes EXP and loot to the player."""
        total_exp = 0
        total_gold = 0

        for enemy in self.enemies:
            total_exp += int(enemy.get_stat("exp_reward") or (enemy.level * 20))
            for loot in enemy.loot_table:
                if loot.get("type") == "gold":
                    chance = loot.get("chance", 1.0)
                    if random.random() <= chance:
                        gold_min = loot.get("min_amount", 1)
                        gold_max = loot.get("max_amount", 5)
                        total_gold += random.randint(gold_min, gold_max)

        self.player.gold += total_gold
        print(f"Loot acquired: {total_gold} Gold! (Total Gold: {self.player.gold})")

        exp_formula = self.settings.get("player", {}).get("exp_formula", "100")
        exp_base = self.settings.get("player", {}).get("exp_base", 100)
        leveled = self.player.add_exp(total_exp, exp_formula, exp_base)

        print(f"Gained {total_exp} EXP! (Current EXP: {self.player.exp}/{self.player.exp_to_next_level})")
        for lvl in leveled:
            print(f"*** LEVEL UP! You reached Level {lvl}! ***")

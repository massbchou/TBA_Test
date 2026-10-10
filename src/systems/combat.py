"""Combat system with speed-based continuous-time turn resolution.

Turn lifecycle:
  1. The living character with the lowest action_time acts (ties: higher speed,
     then the player, then list order).
  2. The clock advances to that time: clock-based timers expire and
     ROUNDS / TIME_UNITS delays fire.
  3. Start of turn: due TURNS delays fire, then on_turn_start status hooks.
  4. The actor acts (player menu or AI).
  5. End of turn: TURNS timers tick, stamina regenerates, on_turn_end hooks run.
  6. action_time += round_time_units // speed.
"""
from __future__ import annotations

import random
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

from src.io.input_provider import AutoInput, InputProvider
from src.rng import get_rng
from src.systems.action_orchestrator import ActionOrchestrator
from src.systems.actions.definitions import SOURCE_ITEM, SOURCE_SPELL, SOURCE_TECHNIQUE, ActionDef, ActionRegistry
from src.systems.ai_controller import AIController
from src.systems.battle import Battle

if TYPE_CHECKING:
    from src.data_loader import DataLoader
    from src.models.character import Character
    from src.models.enemy import Enemy
    from src.models.player import Player
    from src.systems.perks import PerkManager

MAX_TURNS = 500


class CombatResult(Enum):
    VICTORY = "victory"
    DEFEAT = "defeat"
    FLED = "fled"


class Combat:
    """Manages tactical turn-based combat encounters."""

    def __init__(
        self,
        player: Player,
        settings: dict[str, Any],
        data_loader: DataLoader | None = None,
        action_orchestrator: ActionOrchestrator | None = None,
        ai_controller: AIController | None = None,
        input_provider: InputProvider | None = None,
        rng: random.Random | None = None,
        narrator: Callable[[str], None] = print,
        perk_manager: PerkManager | None = None,
        run_stats: dict[str, Any] | None = None,
    ):
        self.player = player
        self.settings = settings
        self.data_loader = data_loader
        combat_cfg = self.settings.get("combat", {})
        self.round_time_units = int(combat_cfg.get("round_time_units", 12500))
        self.resource_regen: dict[str, int] = dict(combat_cfg.get("resource_regen", {}))
        if not self.resource_regen and combat_cfg.get("stamina_regen_per_turn"):
            self.resource_regen = {"stamina": int(combat_cfg["stamina_regen_per_turn"])}
        self.post_victory_restore = float(combat_cfg.get("post_victory_restore", 0))
        self.min_speed_fraction = float(combat_cfg.get("min_speed_fraction", 0.5))
        self.actions: ActionRegistry = data_loader.actions if data_loader else ActionRegistry.build()
        self.action_orchestrator = action_orchestrator or ActionOrchestrator(data_loader)
        self.ai_controller = ai_controller or AIController(data_loader, actions=self.actions)
        self.input = input_provider or AutoInput()
        self.rng = rng or get_rng()
        self.narrate = narrator
        self.perk_manager = perk_manager
        self.run_stats = run_stats if run_stats is not None else {}
        self.enemies: list[Enemy] = []
        self.battle: Battle | None = None

    # --------------------------------------------------------------- loop

    def run(self, encounter: list[Enemy], subtype: str = "Regular") -> CombatResult:
        """Executes a combat encounter until victory, defeat, or escape."""
        self.enemies = encounter
        disallowed = self.settings.get("combat", {}).get("run", {}).get("disallowed_subtypes", ["Boss"])
        battle = Battle(
            self.player,
            self.enemies,
            orchestrator=self.action_orchestrator,
            rng=self.rng,
            input_provider=self.input,
            statuses=self.data_loader.status_defs if self.data_loader else {},
            settings=self.settings,
            narrator=self.narrate,
            allow_run=subtype not in disallowed,
        )
        self.battle = battle

        self.narrate("\n================== COMBAT STARTS ==================")
        self.narrate(f"Hero: {self.player.name} (HP: {self.player.health}/{self.player.get_stat('max_health')}, Speed: {self.player.get_stat('speed')})")
        for enemy in self.enemies:
            if enemy.intro:
                self.narrate(f"  {enemy.intro}")
        for enemy in self.enemies:
            self.narrate(f"Enemy: {enemy.name} (HP: {enemy.health}/{enemy.get_stat('max_health')}, Speed: {enemy.get_stat('speed')})")

        for p in battle.participants:
            p.action_time = 0
            p.turn_count = 0

        turns = 0
        while not battle.is_over():
            actor = self._next_actor(battle)
            battle.advance_clock(actor.action_time)
            if battle.is_over():
                break
            if not actor.is_alive():
                continue

            battle.start_turn(actor)
            if actor.is_alive() and not battle.is_over():
                if actor is self.player:
                    self._process_player_turn(battle)
                else:
                    self._process_enemy_turn(actor, battle)  # type: ignore[arg-type]
            if actor.is_alive():
                for resource, amount in self.resource_regen.items():
                    actor.restore_resource(resource, amount)
            battle.end_turn(actor)

            actor.action_time += max(1, self.round_time_units // self._turn_speed(actor))

            turns += 1
            if turns >= MAX_TURNS:
                self.narrate("The battle drags on endlessly... both sides withdraw.")
                battle.fled = True

        result = self._result(battle)
        for char in battle.participants:
            char.clear_combat_state()
        battle.scheduler.clear()

        if result is CombatResult.VICTORY:
            self.narrate("\n>>> VICTORY! All enemies have been defeated! <<<")
            self.run_stats["enemies_defeated"] = self.run_stats.get("enemies_defeated", 0) + len(self.enemies)
            if self.post_victory_restore:
                for res in self.player.resources.values():
                    res.current = min(res.maximum, res.current + int(res.maximum * self.post_victory_restore))
            self._process_post_combat_rewards()
        elif result is CombatResult.FLED:
            self.narrate("\n>>> You escaped the battle. <<<")
        else:
            self.narrate("\n>>> DEFEAT! You have fallen in battle... <<<")
            self.run_stats["cause_of_death"] = ", ".join(e.name for e in self.enemies)
        return result

    def _result(self, battle: Battle) -> CombatResult:
        if not self.player.is_alive():
            return CombatResult.DEFEAT
        if battle.fled:
            return CombatResult.FLED
        return CombatResult.VICTORY

    def _turn_speed(self, actor: Character) -> int:
        """Speed used for turn cost. Debuffs can't push it below ``min_speed_fraction`` of base speed,
        so stacked slows can never lock a character out of the fight."""
        floor = actor.base_stat("speed") * self.min_speed_fraction
        return max(1, int(max(actor.get_stat("speed"), floor)))

    @staticmethod
    def _next_actor(battle: Battle) -> Character:
        living = [(i, c) for i, c in enumerate(battle.participants) if c.is_alive()]
        _, actor = min(
            living,
            key=lambda pair: (
                pair[1].action_time,
                -pair[1].get_stat("speed"),
                0 if battle.is_player(pair[1]) else 1,
                pair[0],
            ),
        )
        return actor

    # ------------------------------------------------------------- player

    def used_resources(self, player: Player) -> set[str]:
        """Resources that some action the player knows actually costs."""
        used: set[str] = set()
        for action_id in player.abilities + player.spells:
            action = self.actions.get(action_id)
            if action is not None:
                used |= set(action.costs)
        return used

    def _status_line(self, char: Character) -> str:
        parts = [f"HP {char.health}/{int(char.get_stat('max_health'))}"]
        shown = self.used_resources(char) if char is self.player else set()
        for name, res in char.resources.items():
            if name in shown:
                parts.append(f"{name.upper()} {res.current}/{res.maximum}")
        if char.statuses:
            parts.append("[" + ", ".join(s.name for s in char.statuses) + "]")
        return f"{char.name}: " + " | ".join(parts)

    def _process_player_turn(self, battle: Battle) -> None:
        """Shows the six-action menu and executes the chosen action."""
        player = self.player
        self.narrate("\n" + self._status_line(player))
        for enemy in battle.enemies_of(player):
            self.narrate("  vs " + self._status_line(enemy))

        menu = ["Attack", "Defend"]
        if player.abilities:
            menu.append("Technique")
        if player.spells:
            menu.append("Cast")
        menu.append("Bag" if self._usable_items() else "Bag (empty)")  # always shown, so numbering stays stable
        menu.append("Run")

        action: ActionDef | None = None
        while action is None:
            choice = menu[self.input.choose("Your move:", menu)]
            if choice == "Attack":
                action = self.actions["attack"]
            elif choice == "Defend":
                action = self.actions["defend"]
            elif choice == "Technique":
                action = self._pick_action("Technique", player.abilities, SOURCE_TECHNIQUE)
            elif choice == "Cast":
                action = self._pick_action("Spell", player.spells, SOURCE_SPELL)
            elif choice.startswith("Bag"):
                action = self._pick_item()
            elif choice == "Run":
                if battle.allow_run:
                    action = self.actions["run"]
                else:
                    self.narrate("There is no escape from this fight!")

        if action.source == SOURCE_ITEM:
            player.remove_item(action.id)
        else:
            player.pay(action.costs)
        self.narrate(f"> {player.name} uses {action.name}!")
        self.action_orchestrator.execute(player, action, battle)

    def _pick_action(self, label: str, known: list[str], source: str) -> ActionDef | None:
        options = [a for a in (self.actions.get(aid) for aid in known) if a is not None and a.source == source]
        if not options:
            self.narrate(f"You don't know any {label.lower()}s.")
            return None
        labels = []
        for a in options:
            cost = ", ".join(f"{v} {k}" for k, v in a.costs.items()) or "free"
            short = "" if self.player.can_afford(a.costs) else "  (not enough resources)"
            labels.append(f"{a.name} ({cost}){short} - {a.description}")
        idx = self.input.choose(f"Choose a {label.lower()}:", labels + ["Back"])
        if idx == len(options):
            return None
        chosen = options[idx]
        if not self.player.can_afford(chosen.costs):
            self.narrate(f"You can't afford {chosen.name} right now.")
            return None
        return chosen

    def _usable_items(self) -> list[tuple[ActionDef, int]]:
        return [
            (self.actions[item_id], qty)
            for item_id, qty in self.player.inventory.items()
            if item_id in self.actions and self.actions[item_id].usable_in_combat and qty > 0
        ]

    def _pick_item(self) -> ActionDef | None:
        stacks = self._usable_items()
        if not stacks:
            self.narrate("Your bag has nothing usable in combat.")
            return None
        labels = [f"{a.name} x{qty} - {a.description}" for a, qty in stacks]
        idx = self.input.choose("Use which item?", labels + ["Back"])
        return None if idx == len(stacks) else stacks[idx][0]

    # -------------------------------------------------------------- enemy

    def _process_enemy_turn(self, enemy: Enemy, battle: Battle) -> None:
        """Executes an enemy turn via AIController."""
        action = self.ai_controller.decide_action(enemy, battle)
        if action is None:
            self.narrate(f"< {enemy.name} waits, gathering its strength.")
            return
        self.narrate(f"< {enemy.name} uses {action.name}!")
        self.action_orchestrator.execute(enemy, action, battle)
        enemy.trigger_cooldowns(action.id)

    # ------------------------------------------------------------ rewards

    def _process_post_combat_rewards(self) -> None:
        """Distributes EXP, gold and item loot, then offers perks for each level gained."""
        total_exp = 0
        total_gold = 0
        items: dict[str, int] = {}

        recovered = sum(getattr(e, "stolen_gold", 0) for e in self.enemies)
        if recovered:
            total_gold += recovered
            self.narrate(f"You take back the {recovered} gold that was stolen from you.")
        for enemy in self.enemies:
            total_exp += int(enemy.get_stat("exp_reward") or (enemy.level * 20))
            for loot in enemy.loot_table:
                if self.rng.random() > loot.get("chance", 1.0):
                    continue
                amount = self.rng.randint(loot.get("min_amount", 1), loot.get("max_amount", 1))
                if loot.get("type") == "gold":
                    total_gold += amount
                elif loot.get("type") == "item" and loot.get("item_id"):
                    items[loot["item_id"]] = items.get(loot["item_id"], 0) + amount

        self.player.gold += total_gold
        self.run_stats["gold_earned"] = self.run_stats.get("gold_earned", 0) + total_gold
        if total_gold:
            self.narrate(f"You find {total_gold} gold. (Gold: {self.player.gold})")
        for item_id, qty in items.items():
            self.player.add_item(item_id, qty)
            name = self.actions[item_id].name if item_id in self.actions else item_id
            self.narrate(f"Found {name} x{qty}!")

        exp_formula = self.settings.get("player", {}).get("exp_formula", "100")
        exp_base = self.settings.get("player", {}).get("exp_base", 100)
        leveled = self.player.add_exp(total_exp, exp_formula, exp_base)

        self.narrate(f"Gained {total_exp} EXP! (Current EXP: {self.player.exp}/{self.player.exp_to_next_level})")
        for lvl in leveled:
            self.narrate(f"*** LEVEL UP! You reached Level {lvl}! ***")
            growth = self.player.apply_growth()
            if growth:
                self.narrate("    " + ", ".join(growth))
            if self.perk_manager is not None:
                self.perk_manager.offer(self.player, lvl)

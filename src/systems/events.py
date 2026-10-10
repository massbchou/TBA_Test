"""Event definitions for road floors: combat, occurrences, and rest stops."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.systems.effects import apply_effects

if TYPE_CHECKING:
    from src.game_state import GameState
    from src.models.enemy import Enemy
    from src.models.player import Player
    from src.systems.combat import Combat

LABEL_TAGS = {"Regular": "Battle", "Ordeal": "Ordeal", "Boss": "Boss", "Rest": "Rest Stop"}


class Event:
    """Base class for all floor events."""

    def __init__(
        self,
        event_id: str,
        event_type: str,
        display_name: str,
        description: str,
        subtype: str = "",
        is_mystery: bool = False,
    ):
        self.id = event_id
        self.type = event_type
        self.display_name = display_name
        self.description = description
        self.subtype = subtype
        self.is_mystery = is_mystery

    def get_choice_label(self) -> str:
        """Text displayed to the player in the path selection screen."""
        if self.is_mystery:
            return "[???] A fog-bound side path"
        tag = LABEL_TAGS.get(self.subtype, "Event")
        return f"[{tag}] {self.display_name}"

    def execute(self, game_state: GameState, combat_system: Combat) -> bool:
        """Executes the event. Returns True if the player can proceed, False if game over."""
        raise NotImplementedError


class CombatEvent(Event):
    """An encounter that initiates combat against one or more enemies."""

    def __init__(
        self,
        event_id: str,
        display_name: str,
        description: str,
        encounter: list[Enemy],
        subtype: str = "Regular",
        is_mystery: bool = False,
    ):
        super().__init__(
            event_id=event_id,
            event_type="Combat",
            display_name=display_name,
            description=description,
            subtype=subtype,
            is_mystery=is_mystery,
        )
        self.encounter = encounter

    def execute(self, game_state: GameState, combat_system: Combat) -> bool:
        from src.systems.combat import CombatResult

        print(f"\n{self.description}")
        return combat_system.run(self.encounter, subtype=self.subtype) is not CombatResult.DEFEAT


# ---------------------------------------------------------------- requirements

def unmet_requirement(player: Player, requires: dict[str, Any] | None) -> str | None:
    """Returns a short description of the first unmet requirement, or None if all are met."""
    if not requires:
        return None
    gold = requires.get("gold")
    if gold is not None and player.gold < gold:
        return f"requires {gold} gold"
    classes = requires.get("class")
    if classes:
        allowed = [classes] if isinstance(classes, str) else list(classes)
        if player.class_name not in allowed:
            return f"{' / '.join(allowed)} only"
    item = requires.get("item")
    if item:
        needed = item if isinstance(item, dict) else {item: 1}
        for item_id, qty in needed.items():
            if player.inventory.get(item_id, 0) < qty:
                return f"requires {item_id.replace('_', ' ')}"
    for stat, minimum in requires.get("stat", {}).items():
        if player.get_stat(stat) < minimum:
            return f"requires {stat.upper()} {minimum}"
    level = requires.get("level")
    if level is not None and player.level < level:
        return f"requires level {level}"
    return None


class OccurrenceEvent(Event):
    """A non-combat scenario with narrative choices.

    A choice may hold ``requires`` (gating), ``effects``, nested ``choices``, a
    ``description``, a ``result_text``, and a ``chance`` with ``success`` /
    ``failure`` outcomes (each shaped like a choice). A ``combat`` effect starts
    a fight with the listed enemies.
    """

    def __init__(
        self,
        event_id: str,
        display_name: str,
        description: str,
        choices: dict[str, Any],
        subtype: str = "Normal",
        is_mystery: bool = False,
        once_per_run: bool = False,
    ):
        super().__init__(
            event_id=event_id,
            event_type="Occurrence",
            display_name=display_name,
            description=description,
            subtype=subtype,
            is_mystery=is_mystery,
        )
        self.choices = choices
        self.once_per_run = once_per_run

    def execute(self, game_state: GameState, combat_system: Combat) -> bool:
        print(f"\n=== {self.display_name} ===")
        print(self.description)
        if self.once_per_run:
            game_state.used_once.add(self.id)
        if not self.choices:
            print("You search around, but find nothing of note. Moving on...")
            return True
        return self._resolve(self.choices, game_state, combat_system)

    def _resolve(self, choices: dict[str, Any], game_state: GameState, combat_system: Combat) -> bool:
        """Prompts for an available choice and resolves it. Returns False if the player died."""
        player = game_state.player
        available = []
        for label, data in choices.items():
            reason = unmet_requirement(player, data.get("requires"))
            if reason:
                print(f"  (locked) {label} - {reason}")
            else:
                available.append(label)
        if not available:
            print("There is nothing you can do here. You move on.")
            return True
        chosen = available[combat_system.input.choose("What do you do?", available)]
        print(f"\nYou choose: {chosen}")
        return self._outcome(choices[chosen], game_state, combat_system)

    def _outcome(self, data: dict[str, Any], game_state: GameState, combat_system: Combat) -> bool:
        if data.get("description"):
            print(data["description"])
        if "chance" in data:
            succeeded = combat_system.rng.random() < float(data["chance"])
            print("(Success!)" if succeeded else "(It doesn't go your way.)")
            branch = data.get("success" if succeeded else "failure", {})
            if not self._outcome(branch, game_state, combat_system):
                return False
        elif "choices" in data:
            return self._resolve(data["choices"], game_state, combat_system)
        else:
            effects = data.get("effects", [])
            # Flavour first, then its mechanical consequences; after a fight the text is the aftermath.
            text_after = any(e.get("type") == "combat" for e in effects)
            if data.get("result_text") and not text_after:
                print(data["result_text"])
            if not self._apply(effects, game_state, combat_system):
                return False
            if data.get("result_text") and text_after:
                print(data["result_text"])
            return True
        if data.get("result_text"):
            print(data["result_text"])
        return True

    def _apply(self, effects: list[dict[str, Any]], game_state: GameState, combat_system: Combat) -> bool:
        from src.systems.combat import CombatResult

        loader = combat_system.data_loader
        for effect in effects:
            if effect.get("type") == "exp":
                from src.formula import evaluate_formula

                amount = evaluate_formula(str(effect["amount"]), floor=game_state.current_level)
                combat_system.grant_exp(max(0, round(amount)))
                continue
            if effect.get("type") == "combat":
                from src.systems.scaling import spawn_level

                floor = game_state.current_level
                enemies = [
                    loader.build_enemy(slug, spawn_level(slug, floor, combat_system.rng, loader.settings, effect.get("levels")))
                    for slug in effect["enemies"]
                ]
                result = combat_system.run(enemies, subtype=effect.get("subtype", "Regular"))
                if result is CombatResult.DEFEAT:
                    return False
                continue
            for msg in apply_effects(game_state.player, [effect], loader):
                print(msg)
        return True


class RestEvent(Event):
    """A waystation: rest to recover, and trade with a travelling merchant if one is present."""

    def __init__(
        self,
        event_id: str = "rest_site",
        display_name: str = "A Waystation Fire",
        description: str = "A sheltered fire where travellers tend their wounds and trade.",
        is_mystery: bool = False,
        stock: list[str] | None = None,
    ):
        super().__init__(
            event_id=event_id,
            event_type="Rest",
            display_name=display_name,
            description=description,
            subtype="Rest",
            is_mystery=is_mystery,
        )
        self.stock = list(stock or [])

    def execute(self, game_state: GameState, combat_system: Combat) -> bool:
        print(f"\n=== {self.display_name} ===")
        print(self.description)
        player = game_state.player
        while True:
            options = ["Rest by the fire"]
            if self.stock:
                options.append("Trade with the merchant")
            options.append("Move on without resting")
            choice = options[combat_system.input.choose(f"(Gold: {player.gold}) What do you do?", options)]
            if choice.startswith("Rest"):
                self._rest(game_state)
                return True
            if choice.startswith("Trade"):
                Shop(self.stock, combat_system).visit(player)
                continue
            return True

    @staticmethod
    def _rest(game_state: GameState) -> None:
        player = game_state.player
        max_hp = int(player.get_stat("max_health"))
        fraction = game_state.settings.get("combat", {}).get("rest_heal_fraction", 0.5)
        healed = player.heal(max(1, int(max_hp * fraction)))
        player.refill_resources()
        if healed:
            print(f"You rest by the warm coals and recover {healed} HP. (HP {player.health}/{max_hp})")
        else:
            print("You rest by the warm coals.")
        if player.resources:
            print("Your stamina and mana are fully restored.")


class Shop:
    """Buy at full price; sell anything with a price at half."""

    SELL_RATE = 0.5
    CHA_DISCOUNT_PER_POINT = 0.02  # each CHA point above 10 takes 2% off, up to 25%
    MAX_DISCOUNT = 0.25

    def __init__(self, stock: list[str], combat_system: Combat):
        self.stock = stock
        self.actions = combat_system.actions
        self.input = combat_system.input

    def buy_price(self, item_id: str, player: Player) -> int:
        import math

        discount = min(self.MAX_DISCOUNT, max(0.0, (player.get_stat("cha") - 10) * self.CHA_DISCOUNT_PER_POINT))
        return math.ceil(self.actions[item_id].price * (1 - discount))

    def sell_price(self, item_id: str) -> int:
        item = self.actions.get(item_id)
        return int(item.price * self.SELL_RATE) if item else 0

    def visit(self, player: Player) -> None:
        print("\nA merchant spreads a blanket of wares by the fire.")
        while True:
            options: list[tuple[str, str, str]] = []
            for item_id in self.stock:
                item = self.actions.get(item_id)
                if item is None:
                    continue
                price = self.buy_price(item_id, player)
                if player.gold >= price:
                    options.append((f"Buy {item.name} ({price}g) - {item.description}", "buy", item_id))
                else:
                    print(f"  (locked) Buy {item.name} - {price}g")
            for item_id, qty in player.inventory.items():
                price = self.sell_price(item_id)
                if price > 0:
                    options.append((f"Sell {self.actions[item_id].name} x{qty} ({price}g each)", "sell", item_id))
            options.append(("Done trading", "done", ""))
            label, kind, item_id = options[self.input.choose(f"(Gold: {player.gold}) Trade:", [o[0] for o in options])]
            if kind == "done":
                return
            name = self.actions[item_id].name
            if kind == "buy":
                player.gold -= self.buy_price(item_id, player)
                player.add_item(item_id)
                print(f"You buy a {name}. (Gold: {player.gold})")
            else:
                player.remove_item(item_id)
                player.gold += self.sell_price(item_id)
                print(f"You sell a {name}. (Gold: {player.gold})")

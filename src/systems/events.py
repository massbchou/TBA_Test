"""Event definitions for dungeon floors."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.systems.effects import apply_effects

if TYPE_CHECKING:
    from src.game_state import GameState
    from src.models.enemy import Enemy
    from src.systems.combat import Combat


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
        """Text displayed to the player in the event selection screen."""
        if self.is_mystery:
            return "??? [Mystery Path] - Proceed into the unknown"
        sub = f" ({self.subtype})" if self.subtype else ""
        return f"[{self.type}{sub}] {self.display_name}"

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


class OccurrenceEvent(Event):
    """A non-combat scenario featuring narrative choices and potential rewards or hazards."""

    def __init__(
        self,
        event_id: str,
        display_name: str,
        description: str,
        choices: dict[str, Any],
        subtype: str = "Normal",
        is_mystery: bool = False,
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

    def execute(self, game_state: GameState, combat_system: Combat) -> bool:
        print(f"\n=== {self.display_name} ===")
        print(self.description)

        if not self.choices:
            print("You search around, but find nothing of note. Moving on...")
            return True

        self._resolve(self.choices, game_state, combat_system)
        return True

    def _resolve(self, choices: dict[str, Any], game_state: GameState, combat_system: Combat) -> None:
        """Prompts for a choice, recursing into nested choices, then applies its effects."""
        labels = list(choices)
        chosen_text = labels[combat_system.input.choose("What do you do?", labels)]
        choice_data = choices[chosen_text]
        print(f"\nYou choose: {chosen_text}")

        if choice_data.get("description"):
            print(choice_data["description"])
        if "choices" in choice_data:
            self._resolve(choice_data["choices"], game_state, combat_system)
            return

        for msg in apply_effects(game_state.player, choice_data.get("effects", []), combat_system.data_loader):
            print(msg)
        if choice_data.get("result_text"):
            print(choice_data["result_text"])


class RestEvent(Event):
    """A safe campsite where the player recovers resources."""

    def __init__(
        self,
        event_id: str = "rest_site",
        display_name: str = "Rest Site",
        description: str = "A sheltered campfire where you can tend to your wounds.",
        is_mystery: bool = False,
    ):
        super().__init__(
            event_id=event_id,
            event_type="Rest",
            display_name=display_name,
            description=description,
            subtype="Rest",
            is_mystery=is_mystery,
        )

    def execute(self, game_state: GameState, combat_system: Combat) -> bool:
        print(f"\n=== {self.display_name} ===")
        print(self.description)
        player = game_state.player
        max_hp = int(player.get_stat("max_health"))
        fraction = game_state.settings.get("combat", {}).get("rest_heal_fraction", 0.5)
        healed = player.heal(max(1, int(max_hp * fraction)))
        player.refill_resources()
        print(f"You rest by the warm coals and recover {healed} HP. (Current HP: {player.health}/{max_hp})")
        if player.resources:
            print("Your stamina and mana are fully restored.")
        return True

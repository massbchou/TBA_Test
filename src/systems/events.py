"""Event definitions for dungeon floors."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
        print(f"\n{self.description}")
        return combat_system.run(self.encounter)


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

        choices_list = list(self.choices.items())
        print("\nWhat do you do?")
        for i, (choice_text, _) in enumerate(choices_list, start=1):
            print(f"  [{i}] {choice_text}")

        # Choose option 1 by default if interactive loop isn't handling input
        chosen_text, choice_data = choices_list[0]
        print(f"\nYou choose: {chosen_text}")

        choice_type = choice_data.get("type")
        if choice_type == "heal":
            amount = choice_data.get("amount", 20)
            healed = game_state.player.heal(amount)
            print(f"You recovered {healed} HP! (Current: {game_state.player.health}/{game_state.player.get_stat('max_health')})")
        elif choice_type == "stat_change":
            stat = choice_data.get("stat")
            val = choice_data.get("value", 0)
            if stat:
                game_state.player.stats[stat] = game_state.player.stats.get(stat, 0) + val
                print(f"Your {stat} changed by {val:+d}!")

        result_text = choice_data.get("result_text")
        if result_text:
            print(result_text)

        return True


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
        heal_amount = max(1, int(max_hp * 0.5))
        healed = player.heal(heal_amount)
        print(f"You rest by the warm coals and recover {healed} HP. (Current HP: {player.health}/{max_hp})")
        return True

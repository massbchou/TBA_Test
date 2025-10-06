class Event:
    """Base class for all game events."""
    def __init__(self, event_id, event_type, description, subtype=None):
        self.id = event_id
        self.type = event_type
        self.description = description
        self.subtype = subtype

    def execute(self, game_state, combat_system):
        """Executes the event's logic. Returns True if the player can continue, False otherwise."""
        raise NotImplementedError

class CombatEvent(Event):
    """An event that initiates combat."""
    def __init__(self, event_id, description, encounter, subtype="Regular"):
        super().__init__(event_id, "Combat", description, subtype)
        self.encounter = encounter # List of Enemy objects

    def execute(self, game_state, combat_system):
        print(f"\n{self.description}")
        return combat_system.run_combat(self.encounter)

class OccurrenceEvent(Event):
    """A text-based event with choices."""
    def __init__(self, event_id, description, choices):
        super().__init__(event_id, "Occurrence", description)
        self.choices = choices

    def execute(self, game_state, combat_system):
        print(self.description)
        # TODO: Implement choice presentation and outcome logic
        print("An occurrence event happened, but choice logic is not implemented yet.")
        return True # Assume success for now

class RestEvent(Event):
    """An event where the player can rest and shop."""
    def __init__(self, event_id, description):
        super().__init__(event_id, "Rest", description)

    def execute(self, game_state, combat_system):
        print(self.description)
        # TODO: Implement rest and shop logic
        player = game_state.player
        hp_to_heal = int(player.get_stat("max_health") * 0.5) # Heal 50%
        player.heal(hp_to_heal)
        print("You rest and recover some health.")
        return True
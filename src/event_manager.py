import random
from src.utils import weighted_choice
from src.events import CombatEvent, OccurrenceEvent, RestEvent
from src.enemy import Enemy

class EventManager:
    """Handles the generation of game events based on settings."""
    def __init__(self, settings, all_events_data, all_enemies_data):
        self.settings = settings
        self.all_events_data = {e["id"]: e for e in all_events_data}
        self.all_enemies_data = {e["id"]: e for e in all_enemies_data}

    def get_next_event_choices(self, game_state):
        """Generates a list of event choices for the player."""
        level = game_state.current_level
        boss_interval = self.settings["combat"].get("boss_event_interval", 0)

        # Boss Event check
        if boss_interval > 0 and level % boss_interval == 0:
            return [self._generate_boss_encounter(level)]

        choices = []
        gen_settings = self.settings["events"]["generation"]

        # Regular event choices
        reg_dist = self.settings["events"]["distributions"]["regular"]["type_weights"]
        for _ in range(gen_settings["next_event_choices"]):
            event_type = weighted_choice(reg_dist)
            event = self._create_event_instance(event_type, game_state, is_mystery=False)
            if event:
                choices.append(event)

        # Mystery event choices
        mys_dist = self.settings["events"]["distributions"]["mystery"]["type_weights"]
        for _ in range(gen_settings["mystery_event_choices"]):
            event_type = weighted_choice(mys_dist)
            event = self._create_event_instance(event_type, game_state, is_mystery=True)
            if event:
                # TODO: Add logic to obscure mystery events
                choices.append(event)

        return choices

    def _create_event_instance(self, event_type, game_state, is_mystery):
        """Factory method to create a specific event object."""
        # This mapping allows for different subtypes of events, e.g. Combat_Ordeal
        event_subtype = None
        if "_" in event_type:
            event_type, event_subtype = event_type.split("_", 1)

        if event_type == "Combat":
            if event_subtype == "Ordeal":
                encounter, desc = self._generate_ordeal_encounter(game_state.current_level)
                return CombatEvent("combat_ordeal", desc, encounter, subtype="Ordeal")
            else: # Regular combat
                encounter, desc = self._generate_regular_combat_encounter(game_state.current_level)
                return CombatEvent("combat_random", desc, encounter, subtype="Regular")

        elif event_type == "Occurrence":
            subtype_tag = "reward" if event_subtype == "Reward" else "normal"
            # TODO: Select a real occurrence event from data filtered by subtype_tag
            return OccurrenceEvent("occurrence_placeholder", f"A path forks before you. It feels {subtype_tag}.", {})

        elif event_type == "Rest":
            return RestEvent("rest_placeholder", "You find a quiet place to rest.")

        return None

    def _get_enemies_by_tags(self, required_tags, categories=None):
        """
        Filters the master enemy list, returning only enemies that have ALL required tags.
        """
        if not isinstance(required_tags, list): required_tags = [required_tags]

        pool = []
        for enemy_data in self.all_enemies_data.values():
            enemy_tags = enemy_data.get("tags", [])
            # AND logic: check if all required tags are present in the enemy's tags
            if all(req_tag in enemy_tags for req_tag in required_tags):
                if categories is None or enemy_data.get("category") in categories:
                    pool.append(enemy_data)
        return pool

    def _get_current_tier_rules(self, current_level):
        """Finds the combat generation rules for the current level."""
        rules = self.settings["combat"]["encounter_generation"]["regular_combat_rules_by_tier"]
        for tier_range, tier_rules in rules.items():
            min_lvl, max_lvl = map(int, tier_range.split('-'))
            if min_lvl <= current_level <= max_lvl:
                return tier_rules
        return None

    def _generate_encounter_from_pool(self, pool, count_weights):
        """Creates a list of enemies from a pool based on weighted counts."""
        if not pool: return []
        num_enemies_str = weighted_choice(count_weights)
        num_enemies = int(num_enemies_str)

        encounter = []
        for _ in range(num_enemies):
            enemy_data = random.choice(pool)
            encounter.append(Enemy(**enemy_data))
        return encounter

    def _generate_regular_combat_encounter(self, level):
        rules = self._get_current_tier_rules(level)
        if not rules: return [], "You encounter nothing."

        pool = self._get_enemies_by_tags(rules["enemy_pool_tags"], categories=["Normal"])
        encounter = self._generate_encounter_from_pool(pool, rules["enemy_count_weights"])
        return encounter, "A group of hostile creatures appears!"

    def _generate_ordeal_encounter(self, level):
        rules = self.settings["combat"]["encounter_generation"]["ordeal_event_rules"]
        # TODO: Add logic for pre-constructed ordeal events

        elite_pool = self._get_enemies_by_tags(rules["random_generation_pool_tags"], categories=["Elite"])
        normal_pool = self._get_enemies_by_tags(rules["random_generation_pool_tags"], categories=["Normal"])

        encounter = []
        encounter += self._generate_encounter_from_pool(elite_pool, rules["random_composition"]["elite_count_weights"])
        encounter += self._generate_encounter_from_pool(normal_pool, rules["random_composition"]["normal_count_weights"])

        return encounter, "A challenging Ordeal blocks your path!"

    def _generate_boss_encounter(self, level):
        # TODO: Select boss based on current tier/level
        boss_pool = self._get_enemies_by_tags([], categories=["Boss"])
        if not boss_pool:
            return RestEvent("error_no_boss", "You reach the heart of the dungeon, but find it empty.")

        boss_data = random.choice(boss_pool)
        encounter = [Enemy(**boss_data)]
        return CombatEvent("combat_boss", f"A powerful boss, {boss_data['name']}, appears!", encounter, subtype="Boss")
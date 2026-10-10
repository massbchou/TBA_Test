"""The camp menu shown between floors: use items, review the character, save and quit."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from src.systems.battle import Battle

if TYPE_CHECKING:
    from src.game_state import GameState
    from src.systems.combat import Combat

CONTINUE = "continue"
QUIT = "quit"


class Camp:
    def __init__(self, combat_system: "Combat", save: Callable[["GameState"], str] | None = None, narrator=print):
        self.combat = combat_system
        self.actions = combat_system.actions
        self.input = combat_system.input
        self.save = save
        self.narrate = narrator

    def usable_items(self, state: "GameState") -> list[str]:
        return [
            item_id for item_id, qty in state.player.inventory.items()
            if qty > 0 and item_id in self.actions and self.actions[item_id].usable_outside_combat
        ]

    def usable_skills(self, state: "GameState") -> list[str]:
        """Known techniques and spells flagged usable outside combat (e.g. Mend) that the player can afford."""
        p = state.player
        return [
            a for a in p.abilities + p.spells
            if a in self.actions and self.actions[a].usable_outside_combat and p.can_afford(self.actions[a].costs)
        ]

    def visit(self, state: "GameState") -> str:
        """Runs the camp menu until the player continues (CONTINUE) or saves and quits (QUIT)."""
        while True:
            options = ["Continue down the road"]
            if self.usable_items(state):
                options.append("Use an item")
            if self.usable_skills(state):
                options.append("Use a skill")
            options.append("Check your character")
            if self.save is not None:
                options.append("Save and quit")
            p = state.player
            prompt = f"Camp (HP {p.health}/{int(p.get_stat('max_health'))}, Gold {p.gold}):"
            choice = options[self.input.choose(prompt, options)]
            if choice.startswith("Continue"):
                return CONTINUE
            if choice == "Use an item":
                self.use_item(state)
            elif choice == "Use a skill":
                self.use_skill(state)
            elif choice.startswith("Check"):
                self.narrate(self.character_sheet(state))
            else:
                path = self.save(state)
                self.narrate(f"Progress saved to {path}. Rest well.")
                return QUIT

    def use_item(self, state: "GameState") -> None:
        player = state.player
        items = self.usable_items(state)
        labels = [f"{self.actions[i].name} x{player.inventory[i]} - {self.actions[i].description}" for i in items]
        idx = self.input.choose("Use which item?", labels + ["Back"])
        if idx == len(items):
            return
        item = self.actions[items[idx]]
        player.remove_item(item.id)
        self.narrate(f"You use the {item.name}.")
        self._run(state, item)

    def use_skill(self, state: "GameState") -> None:
        player = state.player
        skills = self.usable_skills(state)
        labels = []
        for a in skills:
            action = self.actions[a]
            cost = ", ".join(f"{v} {k}" for k, v in action.costs.items()) or "free"
            labels.append(f"{action.name} ({cost}) - {action.description}")
        idx = self.input.choose("Use which skill?", labels + ["Back"])
        if idx == len(skills):
            return
        action = self.actions[skills[idx]]
        player.pay(action.costs)
        self._run(state, action)

    def _run(self, state: "GameState", action) -> None:
        battle = Battle(state.player, [], orchestrator=self.combat.action_orchestrator, rng=self.combat.rng,
                        input_provider=self.input, settings=self.combat.settings, narrator=self.narrate)
        self.combat.action_orchestrator.execute(state.player, action, battle, log=False)

    @staticmethod
    def _hp_breakdown(p) -> str:
        """Explains derived Max HP, e.g. ' (40 base + 6 x CON 15 + 15 bonus)'."""
        if "max_health" not in p.derived_formulas:
            return ""
        bonus = int(p.stats.get("hp_bonus", 0))
        derived = int(p.get_stat("max_health")) - bonus
        text = f" (CON {int(p.base_stat('con'))} gives {derived}"
        return text + (f", +{bonus} bonus)" if bonus else ")")

    def character_sheet(self, state: "GameState") -> str:
        p = state.player
        stats = " ".join(f"{k.upper()} {int(p.get_stat(k))}" for k in ("str", "dex", "con", "int", "wis", "cha"))
        lines = [
            f"\n--- {p.name}, Level {p.level} {p.class_name} ---",
            f"HP {p.health}/{int(p.get_stat('max_health'))}{self._hp_breakdown(p)} | DEF {int(p.get_stat('defense'))} | "
            f"SPEED {int(p.get_stat('speed'))} | Gold {p.gold} | EXP {p.exp}/{p.exp_to_next_level}",
            stats,
        ]
        for name, res in p.resources.items():
            if name in self.combat.used_resources(p):
                lines.append(f"{name.upper()} {res.current}/{res.maximum}")
        for title, ids in (("Techniques", p.abilities), ("Spells", p.spells)):
            for action_id in ids:
                a = self.actions.get(action_id)
                if a:
                    cost = ", ".join(f"{v} {k}" for k, v in a.costs.items()) or "free"
                    lines.append(f"  {title[:-1]}: {a.name} ({cost}) - {a.description}")
        if p.inventory:
            lines.append("Bag: " + ", ".join(f"{self.actions[i].name if i in self.actions else i} x{q}"
                                            for i, q in p.inventory.items()))
        if p.perks:
            loader = self.combat.data_loader
            names = [loader.perk_name(pid) for pid in p.perks] if loader else p.perks
            lines.append("Perks: " + ", ".join(names))
        return "\n".join(lines)

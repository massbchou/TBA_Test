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

    def visit(self, state: "GameState") -> str:
        """Runs the camp menu until the player continues (CONTINUE) or saves and quits (QUIT)."""
        while True:
            options = ["Continue down the road"]
            if self.usable_items(state):
                options.append("Use an item")
            options.append("Check your character")
            if self.save is not None:
                options.append("Save and quit")
            choice = options[self.input.choose("Camp:", options)]
            if choice.startswith("Continue"):
                return CONTINUE
            if choice.startswith("Use"):
                self.use_item(state)
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
        battle = Battle(player, [], orchestrator=self.combat.action_orchestrator, rng=self.combat.rng,
                        input_provider=self.input, settings=self.combat.settings, narrator=self.narrate)
        self.narrate(f"You use the {item.name}.")
        self.combat.action_orchestrator.execute(player, item, battle, log=False)

    def character_sheet(self, state: "GameState") -> str:
        p = state.player
        stats = " ".join(f"{k.upper()} {int(p.get_stat(k))}" for k in ("str", "dex", "con", "int", "wis", "cha"))
        lines = [
            f"\n--- {p.name}, Level {p.level} {p.class_name} ---",
            f"HP {p.health}/{int(p.get_stat('max_health'))} | DEF {int(p.get_stat('defense'))} | "
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
            lines.append("Perks: " + ", ".join(p.perks))
        return "\n".join(lines)

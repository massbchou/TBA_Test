"""Batch playtest: many seeded runs per class, summarised for balance and UX review.

Usage (from the repo root):

    python3 tools/playtest.py                         # heuristic policy, 100 runs per class
    python3 tools/playtest.py --policy random --runs 300
    python3 tools/playtest.py --policy attack --classes Warrior Cleric

Policies:
    attack     always chooses Attack
    random     weighted-random menu choices (covers every action)
    heuristic  heals when low, uses its best affordable skill, steers toward rests when wounded
"""
from __future__ import annotations

import argparse
import collections
import io
import random
import re
import sys
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_loader import DataLoader  # noqa: E402
from src.game_state import GameState  # noqa: E402
from src.models.player import Player  # noqa: E402
from src.systems.camp import Camp  # noqa: E402
from src.systems.combat import Combat  # noqa: E402
from src.systems.event_manager import EventManager  # noqa: E402
from src.systems.events import CombatEvent  # noqa: E402
from src.systems.perks import PerkManager  # noqa: E402

MENU = "Your move:"
PATH = "You perceive multiple paths ahead:"
CAMP = "Camp"
SUBMENUS = ("Choose a technique", "Choose a spell", "Use which item")
DAMAGE_RE = re.compile(r"^  (.+) takes (\d+) (\w+) damage")
MAX_CHOICES = 20_000  # guards against policies that loop on dead-end menus
BASIC_ACTIONS = {"Attack", "Defend", "Run"}


class Policy:
    """Base InputProvider with access to the player it is playing and the action registry."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.player: Player | None = None
        self.actions = None
        self.choices = 0

    def choose(self, prompt: str, options: list[str]) -> int:
        self.choices += 1
        if self.choices > MAX_CHOICES:
            raise RuntimeError(f"Policy appears stuck at {prompt!r}: {options}")
        return self.decide(prompt, options)

    def ask_text(self, prompt: str, default: str) -> str:
        return default

    def decide(self, prompt: str, options: list[str]) -> int:
        if prompt.startswith(CAMP):
            return 0
        return self.rng.randrange(len(options))

    def action_for(self, label: str):
        """The ActionDef a menu label refers to (labels start with the action's name)."""
        for action in self.actions.all():
            if label.startswith(action.name + " "):
                return action
        return None


class AttackPolicy(Policy):
    def decide(self, prompt, options):
        if prompt == MENU:
            return 0
        if prompt.startswith("(Gold:") and "What do you do?" in prompt:
            return 0  # rest
        return super().decide(prompt, options)


class RandomPolicy(Policy):
    MENU_WEIGHTS = {"Attack": 3, "Defend": 1, "Technique": 3, "Cast": 3, "Bag": 1, "Run": 0.2}

    def decide(self, prompt, options):
        if prompt == MENU:
            weights = [0 if o.endswith("(empty)") else self.MENU_WEIGHTS[o.split()[0]] for o in options]
            return self.rng.choices(range(len(options)), weights)[0]
        return super().decide(prompt, options)


class HeuristicPolicy(Policy):
    """Heals when low, otherwise uses an affordable damaging skill; uses the camp, rests and shop sensibly."""

    def __init__(self, rng):
        super().__init__(rng)
        self.want = "offensive"
        self.attack_next = False
        self.shopped = False

    def _hp_below(self, fraction: float) -> bool:
        return self.player.health < fraction * self.player.get_stat("max_health")

    def _heal_items(self) -> list[str]:
        return [i for i, q in self.player.inventory.items() if q and i in self.actions and self.actions[i].has_tag("healing")]

    def _knows(self, tag: str, ids: list[str]) -> bool:
        return any(self.actions[a].has_tag(tag) and self.player.can_afford(self.actions[a].costs) for a in ids if a in self.actions)

    def decide(self, prompt, options):
        p = self.player
        if prompt == MENU:
            if self.attack_next:
                self.attack_next = False
                return 0
            if self._hp_below(0.4):
                self.want = "healing"
                if self._knows("healing", p.spells) and "Cast" in options:
                    return options.index("Cast")
                if self._knows("healing", p.abilities) and "Technique" in options:
                    return options.index("Technique")
                if self._heal_items() and "Bag" in options:
                    return options.index("Bag")
            self.want = "offensive"
            menus = [m for m, ids in (("Technique", p.abilities), ("Cast", p.spells))
                     if m in options and self._knows("offensive", ids)]
            return options.index(self.rng.choice(menus)) if menus else 0
        if prompt.startswith(SUBMENUS):
            usable = [(i, self.action_for(o)) for i, o in enumerate(options[:-1]) if "not enough" not in o]
            matching = [i for i, a in usable if a is not None and a.has_tag(self.want)]
            if matching:
                return self.rng.choice(matching)
            self.attack_next = True
            return len(options) - 1  # Back
        if prompt.startswith(CAMP):
            if self._hp_below(0.5) and "Use an item" in options and self._heal_items():
                self.want = "healing"
                return options.index("Use an item")
            return 0
        if prompt.startswith("(Gold:") and "What do you do?" in prompt:
            if not self.shopped and p.gold >= 30 and any(o.startswith("Trade") for o in options):
                self.shopped = True
                return [i for i, o in enumerate(options) if o.startswith("Trade")][0]
            self.shopped = False
            return 0  # rest
        if prompt.startswith("(Gold:") and "Trade:" in prompt:
            if len(self._heal_items()) < 3 or sum(p.inventory.get(i, 0) for i in self._heal_items()) < 3:
                for i, o in enumerate(options):
                    a = self.action_for(o[4:]) if o.startswith("Buy ") else None
                    if a is not None and a.has_tag("healing"):
                        return i
            return len(options) - 1  # Done
        if prompt == PATH:
            if self._hp_below(0.6):
                for i, o in enumerate(options):
                    if o.startswith(("[Rest Stop]", "[Event]")):
                        return i
            for i, o in enumerate(options):
                if not o.startswith(("[???]", "[Ordeal]")):
                    return i
            return 0
        return super().decide(prompt, options)


POLICIES = {"attack": AttackPolicy, "random": RandomPolicy, "heuristic": HeuristicPolicy}


@dataclass
class RunResult:
    floor: int = 0
    cleared: bool = False
    killer: str | None = None
    boss: str | None = None
    level_at_boss: int | None = None
    combats: list[tuple[str, list[str]]] = field(default_factory=list)


def play(class_name: str, seed: int, policy_name: str, floors: int) -> RunResult:
    rng = random.Random(seed)
    loader = DataLoader()
    loader.load_all()
    policy = POLICIES[policy_name](random.Random(seed + 10_000))
    policy.actions = loader.actions
    log: list[str] = []
    player = loader.build_player(class_name, "Hero")
    policy.player = player
    state = GameState(player, loader.settings)
    perks = PerkManager(loader.level_up_perks, loader.settings, policy, rng, loader, narrator=log.append)
    combat = Combat(player, loader.settings, loader, input_provider=policy, rng=rng,
                    narrator=log.append, perk_manager=perks, run_stats=state.run_stats)
    camp = Camp(combat, narrator=log.append)
    events = EventManager(loader, rng)
    result = RunResult()
    with redirect_stdout(io.StringIO()):
        while True:
            result.floor = state.current_level
            if state.current_level > 1:
                camp.visit(state)
            options = events.generate_choices(state)
            event = options[policy.choose(PATH, [e.get_choice_label() for e in options])]
            if isinstance(event, CombatEvent) and event.subtype == "Boss":
                result.level_at_boss = player.level
            start = len(log)
            survived = event.execute(state, combat)
            if isinstance(event, CombatEvent):
                result.combats.append((event.subtype, log[start:]))
                if event.subtype == "Boss":
                    result.boss = event.display_name
            if not survived:
                result.killer = state.run_stats.get("cause_of_death") or event.display_name
                break
            if state.current_level >= floors:
                result.cleared = True
                break
            state.advance_level()
    return result


def summarize(class_name: str, runs: list[RunResult], actions=None) -> None:
    n = len(runs)
    avg = lambda xs: sum(xs) / max(1, len(xs))  # noqa: E731
    uses: collections.Counter = collections.Counter()
    dealt: collections.Counter = collections.Counter()
    taken: collections.Counter = collections.Counter()
    unaffordable = waits = one_damage = hits = 0
    turns_per_combat = []
    for run in runs:
        for _, lines in run.combats:
            turns = 0
            for line in lines:
                if line.startswith("> "):
                    turns += 1
                    uses[line.split(" uses ", 1)[1].rstrip("!")] += 1
                elif "can't afford" in line:
                    unaffordable += 1
                elif " waits" in line:
                    waits += 1
                match = DAMAGE_RE.match(line)
                if match:
                    amount = int(match.group(2))
                    hits += 1
                    one_damage += amount == 1
                    (taken if match.group(1) == "Hero" else dealt)[match.group(3)] += amount
            turns_per_combat.append(turns)
    killers = collections.Counter(r.killer.split(",")[0] for r in runs if r.killer)
    death_floors = collections.Counter(r.floor for r in runs if not r.cleared)
    skill_turns = sum(n for name, n in uses.items() if name not in BASIC_ACTIONS
                      and not (actions and any(a.name == name and a.source == "item" for a in actions.all())))
    total_turns = sum(uses.values())
    levels = collections.Counter(r.level_at_boss for r in runs if r.level_at_boss is not None)
    print(f"\n== {class_name}: avg floor {avg([r.floor for r in runs]):.1f} | boss reached "
          f"{sum(1 for r in runs if r.boss)}/{n} | cleared {sum(r.cleared for r in runs)}/{n} | "
          f"player turns/combat {avg(turns_per_combat):.1f}")
    print(f"   skill share {skill_turns / max(1, total_turns):.0%} | deaths by floor: {dict(sorted(death_floors.items()))}")
    print(f"   killers: {dict(killers.most_common(5))}")
    print(f"   level when facing boss: {dict(sorted(levels.items()))}")
    print(f"   actions used: {dict(uses.most_common(8))}")
    print(f"   damage dealt by type: {dict(dealt.most_common(6))} | taken: {dict(taken.most_common(4))}")
    print(f"   unaffordable picks {unaffordable}, enemy waits {waits}, 1-damage hits {one_damage}/{hits}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--policy", choices=sorted(POLICIES), default="heuristic")
    parser.add_argument("--runs", type=int, default=100, help="seeded runs per class")
    parser.add_argument("--classes", nargs="*", help="classes to test (default: all)")
    parser.add_argument("--floors", type=int, default=10)
    args = parser.parse_args(argv)

    loader = DataLoader()
    loader.load_all()
    classes = args.classes or list(loader.starting_classes)
    print(f"Policy: {args.policy} | {args.runs} runs per class | floors 1-{args.floors}")
    for class_name in classes:
        summarize(class_name, [play(class_name, seed, args.policy, args.floors) for seed in range(args.runs)], loader.actions)


if __name__ == "__main__":
    main()

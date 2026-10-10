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
from src.systems.combat import Combat  # noqa: E402
from src.systems.event_manager import EventManager  # noqa: E402
from src.systems.events import CombatEvent  # noqa: E402
from src.systems.perks import PerkManager  # noqa: E402

MENU = "Your move:"
PATH = "You perceive multiple paths ahead:"
SUBMENUS = ("Choose a technique", "Choose a spell", "Use which item")
DAMAGE_RE = re.compile(r"^  (.+) takes (\d+) (\w+) damage")
MAX_CHOICES = 20_000  # guards against policies that loop on dead-end menus


class Policy:
    """Base InputProvider with access to the player it is playing."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.player: Player | None = None
        self.choices = 0

    def choose(self, prompt: str, options: list[str]) -> int:
        self.choices += 1
        if self.choices > MAX_CHOICES:
            raise RuntimeError(f"Policy appears stuck at {prompt!r}: {options}")
        return self.decide(prompt, options)

    def decide(self, prompt: str, options: list[str]) -> int:
        return self.rng.randrange(len(options))


class AttackPolicy(Policy):
    def decide(self, prompt, options):
        return 0 if prompt == MENU else super().decide(prompt, options)


class RandomPolicy(Policy):
    MENU_WEIGHTS = [3, 1, 3, 3, 1, 0.2]  # Attack, Defend, Technique, Cast, Bag, Run

    def decide(self, prompt, options):
        if prompt == MENU:
            return self.rng.choices(range(len(options)), self.MENU_WEIGHTS)[0]
        return super().decide(prompt, options)


class HeuristicPolicy(Policy):
    HEALS = ("Heal Wounds", "First Aid", "Healing Grape (Bunch)", "Healing Grape", "Rehabilitate")
    HEAL_ITEMS = ("healing_grape", "healing_grape_bunch")
    REFILLS = ("Inspiriting Plum", "Energizing Pomegranate", "Rest")

    def __init__(self, rng):
        super().__init__(rng)
        self.intent: tuple[str, ...] = ()
        self.attack_next = False

    def _low(self, fraction: float) -> bool:
        return self.player.health < fraction * self.player.get_stat("max_health")

    def decide(self, prompt, options):
        p = self.player
        if prompt == MENU:
            if self.attack_next:
                self.attack_next = False
                return 0
            if self._low(0.4):
                self.intent = self.HEALS
                if any(p.inventory.get(k) for k in self.HEAL_ITEMS):
                    return options.index("Bag")
                if "heal_wounds" in p.spells:
                    return options.index("Cast")
                if {"first_aid", "rehabilitate"} & set(p.abilities):
                    return options.index("Technique")
                return 0
            self.intent = ()  # any damaging option
            menus = [m for m, known in (("Technique", p.abilities), ("Cast", p.spells)) if known]
            return options.index(self.rng.choice(menus)) if menus else 0
        if prompt.startswith(SUBMENUS):
            usable = [(i, o) for i, o in enumerate(options[:-1]) if "not enough" not in o]
            for wanted in self.intent + self.REFILLS:
                for i, o in usable:
                    if o.startswith(wanted + " "):
                        return i
            if not self.intent and prompt.startswith(("Choose a technique", "Choose a spell")):
                offensive = [i for i, o in usable if not o.startswith(self.HEALS + self.REFILLS)]
                if offensive:
                    return self.rng.choice(offensive)
            self.attack_next = True
            return len(options) - 1  # Back
        if prompt == PATH:
            if self._low(0.6):
                for i, o in enumerate(options):
                    if "Rest" in o or "Occurrence" in o:
                        return i
            for i, o in enumerate(options):
                if "Mystery" not in o and "Ordeal" not in o:
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
    log: list[str] = []
    player = loader.build_player(class_name, "Hero")
    policy.player = player
    state = GameState(player, loader.settings)
    perks = PerkManager(loader.level_up_perks, loader.settings, policy, rng, loader, narrator=log.append)
    combat = Combat(player, loader.settings, loader, input_provider=policy, rng=rng,
                    narrator=log.append, perk_manager=perks)
    events = EventManager(loader, rng)
    result = RunResult()
    with redirect_stdout(io.StringIO()):
        while True:
            result.floor = state.current_level
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
                result.killer = re.sub(r"^(Battle|Ordeal|BOSS): ", "", event.display_name)
                break
            if state.current_level >= floors:
                result.cleared = True
                break
            state.advance_level()
    return result


def summarize(class_name: str, runs: list[RunResult]) -> None:
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
    levels = collections.Counter(r.level_at_boss for r in runs if r.level_at_boss is not None)
    print(f"\n== {class_name}: avg floor {avg([r.floor for r in runs]):.1f} | boss reached "
          f"{sum(1 for r in runs if r.boss)}/{n} | cleared {sum(r.cleared for r in runs)}/{n} | "
          f"player turns/combat {avg(turns_per_combat):.1f}")
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
        summarize(class_name, [play(class_name, seed, args.policy, args.floors) for seed in range(args.runs)])


if __name__ == "__main__":
    main()

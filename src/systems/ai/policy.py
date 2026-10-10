"""How an AI caster resolves a CHOICE targeting mode.

An action may name a policy with ``"ai_target"``; otherwise one is chosen by verb.
Register new policies with ``@register_policy``.
"""
from __future__ import annotations

import random
from typing import Callable, Sequence

Policy = Callable[[Sequence, int, object, random.Random], list]
POLICIES: dict[str, Policy] = {}

VERB_DEFAULTS = {
    "HEAL": "lowest_hp_pct",
    "DAMAGE": "lowest_hp",
    "DEBUFF": "lowest_hp",
    "APPLY": "lowest_hp",
    "BUFF": "self_first",
    "SET": "self_first",
    "RESTORE": "self_first",
    "CLEANSE": "self_first",
}


def register_policy(name: str) -> Callable[[Policy], Policy]:
    def decorator(fn: Policy) -> Policy:
        POLICIES[name] = fn
        return fn
    return decorator


@register_policy("lowest_hp")
def _lowest_hp(pool, n, caster, rng):
    return sorted(pool, key=lambda c: c.health)[:n]


@register_policy("lowest_hp_pct")
def _lowest_hp_pct(pool, n, caster, rng):
    return sorted(pool, key=lambda c: c.get_stat("hp_percentage"))[:n]


@register_policy("highest_hp")
def _highest_hp(pool, n, caster, rng):
    return sorted(pool, key=lambda c: -c.health)[:n]


@register_policy("random")
def _random(pool, n, caster, rng):
    return rng.sample(list(pool), n)


@register_policy("self_first")
def _self_first(pool, n, caster, rng):
    chosen = [c for c in pool if c is caster][:n]
    rest = [c for c in pool if c is not caster]
    return chosen + rng.sample(rest, n - len(chosen))


def select(policy: str | None, verb: str, pool: Sequence, n: int, caster: object, rng: random.Random) -> list:
    name = policy or VERB_DEFAULTS.get(verb, "random")
    return POLICIES.get(name, _random)(pool, n, caster, rng)

"""Level-up stat points.

Each level-up grants N points, where N is drawn from a "flattened bell" centred on
the level just reached and never below a floor L:

    with probability flat_share:  N = randint(L, 2 * level)
    otherwise:                    N = round(gauss(level, spread * level))
    N = max(L, N)

Each point independently lands on one of the six primary stats, weighted by the
class's ``stat_weights``. The class bias fades as N rises above the floor, so a big
roll gives more points that are less specialised:

    surplus  = (N - L) / level
    exponent = 1 / (1 + surplus)
    weight'  = class_weight ** exponent
"""
from __future__ import annotations

import random
from collections import Counter
from typing import Any

from src.stats import PRIMARY_STATS

DEFAULTS = {"floor": 1, "spread": 0.6, "flat_share": 0.5}


def roll_point_count(level: int, rng: random.Random, cfg: dict[str, Any] | None = None) -> int:
    cfg = {**DEFAULTS, **(cfg or {})}
    floor = int(cfg["floor"])
    if rng.random() < cfg["flat_share"]:
        n = rng.randint(floor, max(floor, 2 * level))
    else:
        n = round(rng.gauss(level, cfg["spread"] * level))
    return max(floor, n)


def point_weights(stat_weights: dict[str, float], count: int, level: int, floor: int = 1) -> dict[str, float]:
    """Class weights flattened by how far ``count`` exceeds the floor (normalised to sum to 1)."""
    surplus = max(0, count - floor) / max(1, level)
    exponent = 1 / (1 + surplus)
    raw = {stat: max(1e-9, float(stat_weights.get(stat, 1))) ** exponent for stat in PRIMARY_STATS}
    total = sum(raw.values())
    return {stat: w / total for stat, w in raw.items()}


def roll_stat_points(
    stat_weights: dict[str, float], level: int, rng: random.Random, cfg: dict[str, Any] | None = None
) -> dict[str, int]:
    """Rolls a level-up: returns {stat: points gained} for the six primaries (zeros omitted)."""
    cfg = {**DEFAULTS, **(cfg or {})}
    count = roll_point_count(level, rng, cfg)
    weights = point_weights(stat_weights, count, level, int(cfg["floor"]))
    stats = list(weights)
    picks = rng.choices(stats, weights=[weights[s] for s in stats], k=count)
    counts = Counter(picks)
    return {stat: counts[stat] for stat in PRIMARY_STATS if counts[stat]}

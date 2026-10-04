"""General helper utilities for dice, random selection, and math."""
from __future__ import annotations

import random
import re
from typing import TypeVar

T = TypeVar("T")

DICE_PATTERN = re.compile(r"^(\d+)d(\d+)(?:([+-])(\d+))?$")


def weighted_choice(choices_dict: dict[T, float | int]) -> T | None:
    """Selects an item based on weights. Returns None if choices_dict is empty or total weight <= 0."""
    if not choices_dict:
        return None

    total_weight = sum(choices_dict.values())
    if total_weight <= 0:
        return None

    rand_val = random.uniform(0, total_weight)
    cumulative = 0.0

    for choice, weight in choices_dict.items():
        if weight <= 0:
            continue
        cumulative += weight
        if rand_val <= cumulative:
            return choice

    # Fallback to last item with positive weight
    for choice, weight in reversed(list(choices_dict.items())):
        if weight > 0:
            return choice
    return None


def roll_dice(dice_str: str) -> int:
    """
    Parses and rolls dice strings like '2d10', '1d6+3', or '3d8-2'.
    If the string is just an integer, returns the integer value.
    """
    dice_str = dice_str.strip()
    if dice_str.isdigit():
        return int(dice_str)

    match = DICE_PATTERN.match(dice_str)
    if not match:
        raise ValueError(f"Invalid dice format: '{dice_str}'")

    num_dice = int(match.group(1))
    sides = int(match.group(2))
    sign = match.group(3)
    mod = int(match.group(4)) if match.group(4) else 0

    total = sum(random.randint(1, sides) for _ in range(num_dice))
    if sign == "+":
        total += mod
    elif sign == "-":
        total -= mod

    return max(0, total)

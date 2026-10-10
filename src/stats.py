"""Canonical stat names and DSL aliases.

Data files use lowercase keys (``str``, ``max_health``); the Action DSL is
case-insensitive and accepts aliases such as ``STR``, ``HP`` and ``MAX_HP``.
"""
from __future__ import annotations

PRIMARY_STATS = ("str", "dex", "con", "int", "wis", "cha")
DERIVED_STATS = ("defense", "max_health", "speed", "luck")
RESOURCES = ("stamina", "mana")

# Pseudo-stats that are read from character state rather than the stats dict.
HEALTH = "health"
HP_PERCENTAGE = "hp_percentage"

_ALIASES = {
    "HP": HEALTH,
    "HEALTH": HEALTH,
    "MAX_HP": "max_health",
    "MAXHP": "max_health",
    "MAX_HEALTH": "max_health",
    "HP_PERCENTAGE": HP_PERCENTAGE,
    "HP_PERCENT": HP_PERCENTAGE,
    "DEF": "defense",
    "SPD": "speed",
}


_DISPLAY = {
    "max_health": "Max HP", "health": "HP", "defense": "Defense", "speed": "Speed", "luck": "Luck",
    "stamina": "Stamina", "mana": "Mana", "max_stamina": "Max Stamina", "max_mana": "Max Mana",
}


def display_name(name: str) -> str:
    """Player-facing stat name: STR/DEX/... for primaries, words for the rest."""
    key = canonical_stat(name)
    if key in PRIMARY_STATS:
        return key.upper()
    if key.endswith("_resistance"):
        return f"{key[:-11].title()} resistance"
    return _DISPLAY.get(key, key.replace("_", " ").title())


def canonical_stat(name: str) -> str:
    """Maps a DSL or data stat name to its canonical lowercase key."""
    return _ALIASES.get(name.upper(), name.lower())


def is_known_stat(name: str) -> bool:
    """True for stats every character implicitly has (hidden stats default to 0)."""
    key = canonical_stat(name)
    return (
        key in PRIMARY_STATS
        or key in DERIVED_STATS
        or key in RESOURCES
        or key in (HEALTH, HP_PERCENTAGE, "max_stamina", "max_mana")
        or key.endswith("_resistance")
        or key.endswith("_regen")
    )

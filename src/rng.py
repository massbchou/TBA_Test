"""Single shared, seedable random number generator.

Every system that needs randomness takes an optional ``rng`` argument and falls
back to this instance, so a whole run can be reproduced with ``--seed``.
"""
from __future__ import annotations

import random

_rng = random.Random()


def get_rng() -> random.Random:
    """Returns the shared game RNG."""
    return _rng


def seed(value: int | None) -> None:
    """Re-seeds the shared game RNG."""
    _rng.seed(value)

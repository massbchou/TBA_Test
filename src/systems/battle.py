"""Battle: the shared state of one combat, used by the Action System and AI.

``Combat`` owns the turn loop and UI; ``Battle`` holds sides, the clock, the
delay scheduler, the combat log and status hook dispatch.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Callable, Sequence

from src.io.input_provider import AutoInput, InputProvider
from src.rng import get_rng
from src.systems.actions.scheduler import Scheduler
from src.systems.combat_log import CombatLog

if TYPE_CHECKING:
    from src.models.character import ActiveStatus, Character
    from src.models.status import StatusDef
    from src.systems.action_orchestrator import ActionOrchestrator

MAX_HOOK_DEPTH = 4
DEFAULT_ROUND_TIME_UNITS = 12500
DEFAULT_REFERENCE_SPEED = 125


class Battle:
    def __init__(
        self,
        player: "Character",
        enemies: Sequence["Character"],
        *,
        orchestrator: "ActionOrchestrator | None" = None,
        rng: random.Random | None = None,
        input_provider: InputProvider | None = None,
        statuses: dict[str, "StatusDef"] | None = None,
        settings: dict[str, Any] | None = None,
        narrator: Callable[[str], None] | None = None,
        allow_run: bool = True,
    ):
        from src.systems.action_orchestrator import ActionOrchestrator

        self.player = player
        self.enemies = list(enemies)
        self.orchestrator = orchestrator or ActionOrchestrator()
        self.rng = rng or get_rng()
        self.input = input_provider or AutoInput()
        self.statuses = statuses or {}
        self.settings = settings or {}
        combat_cfg = self.settings.get("combat", {})
        self.round_time_units = int(combat_cfg.get("round_time_units", DEFAULT_ROUND_TIME_UNITS))
        self.reference_speed = int(combat_cfg.get("reference_speed", DEFAULT_REFERENCE_SPEED))
        self.round_length = self.round_time_units / self.reference_speed
        self.narrator = narrator or (lambda text: None)
        self.allow_run = allow_run
        self.clock = 0.0
        self.fled = False
        self.log = CombatLog()
        self.scheduler = Scheduler()
        self._hook_depth = 0

    # ------------------------------------------------------------- sides

    @property
    def participants(self) -> list["Character"]:
        return [self.player] + self.enemies

    def is_player(self, char: "Character") -> bool:
        return char is self.player

    def allies_of(self, char: "Character") -> list["Character"]:
        """Living members of char's side, including char."""
        side = [self.player] if self.is_player(char) else self.enemies
        return [c for c in side if c.is_alive()]

    def enemies_of(self, char: "Character") -> list["Character"]:
        side = self.enemies if self.is_player(char) else [self.player]
        return [c for c in side if c.is_alive()]

    def is_over(self) -> bool:
        return self.fled or not self.player.is_alive() or not any(e.is_alive() for e in self.enemies)

    def narrate(self, text: str) -> None:
        self.narrator(text)

    def on_defeat(self, char: "Character") -> None:
        self.narrate(f"  {char.name} is defeated!")
        self.scheduler.cancel_for(char)

    # -------------------------------------------------------------- time

    def advance_clock(self, clock: float) -> None:
        """Moves the clock forward, expiring clock timers and firing due delays."""
        self.clock = max(self.clock, clock)
        for char in self.participants:
            if char.is_alive():
                for status in char.expire_clock(self.clock):
                    self.narrate(f"  {char.name}'s {status.name} wears off.")
                    self.run_status_hook(char, status, "on_expire")
        for pending in self.scheduler.due_at_clock(self.clock):
            pending.fire()

    def start_turn(self, char: "Character") -> None:
        char.turn_count += 1
        for pending in self.scheduler.due_for_turn(char):
            pending.fire()
        if char.is_alive():
            self.emit("on_turn_start", char)

    def end_turn(self, char: "Character") -> None:
        if not char.is_alive():
            return
        for status in char.tick_turn_timers():
            self.narrate(f"  {char.name}'s {status.name} wears off.")
            self.run_status_hook(char, status, "on_expire")
        self.emit("on_turn_end", char)

    # ------------------------------------------------------------- hooks

    def emit(self, hook: str, bearer: "Character") -> None:
        for status in list(bearer.statuses):
            if not bearer.is_alive():
                return
            self.run_status_hook(bearer, status, hook)

    def run_status_hook(self, bearer: "Character", status: "ActiveStatus", hook: str) -> None:
        status_def = self.statuses.get(status.name)
        script = status_def.hooks.get(hook) if status_def else None
        if not script or self._hook_depth >= MAX_HOOK_DEPTH:
            return
        self._hook_depth += 1
        try:
            for _ in range(max(1, status.stacks)):
                if not bearer.is_alive():
                    break
                self.orchestrator.execute_string(bearer, script, self, source=f"status:{status.name}")
        finally:
            self._hook_depth -= 1

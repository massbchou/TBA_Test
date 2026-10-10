"""Action System Orchestrator.

Single entry point for executing any action: Action Strings run through the
Lexer -> Parser -> Target Resolver -> Command Executor pipeline in
``src.systems.actions``; Predefined Actions dispatch to registered Python
functions. See docs/action_system.md.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from src.systems.actions.context import ActionResult, ExecutionContext
from src.systems.actions.executor import run_program
from src.systems.actions.nodes import Program
from src.systems.actions.parser import parse_program
from src.systems.actions.predefined import PREDEFINED

if TYPE_CHECKING:
    from src.models.character import Character
    from src.systems.actions.definitions import ActionDef
    from src.systems.battle import Battle

logger = logging.getLogger("textrogue.actions")


class ActionOrchestrator:
    """Executes ActionDefs and ad-hoc action strings."""

    def __init__(self, data_loader: Any = None):
        self.data_loader = data_loader
        self._cache: dict[str, Program] = {}

    def program_for(self, text: str, source: str = "") -> Program:
        program = self._cache.get(text)
        if program is None:
            program = parse_program(text, source=source)
            for diag in program.diagnostics:
                logger.warning("%s", diag)
            self._cache[text] = program
        return program

    def execute(self, caster: "Character", action: "ActionDef", battle: "Battle", log: bool = True) -> ActionResult:
        """Executes an action and records it in the combat log.

        Costs and cooldowns are the caller's responsibility (see Combat). An action's
        optional ``message`` (e.g. a boss telegraph) is narrated first; ``{caster}``
        is replaced with the caster's name.
        """
        if action.message:
            battle.narrate(f"  {action.message.replace('{caster}', caster.name)}")
        if action.predefined is not None:
            name = action.predefined.get("name")
            fn = PREDEFINED.get(name)
            if fn is None:
                logger.warning("Unknown predefined action %r on %s", name, action.id)
                result = ActionResult(action.id, caster.name)
            else:
                result = fn(self, caster, action, battle, dict(action.predefined.get("params", {})))
        else:
            program = action.program or self.program_for(action.action_string or "", source=action.id)
            result = self._run(caster, program, battle, action)
        if log:
            battle.log.record(caster, action, result.affected)
        return result

    def execute_string(
        self,
        caster: "Character",
        text: str,
        battle: "Battle",
        action: "ActionDef | None" = None,
        source: str = "",
    ) -> ActionResult:
        """Runs an action string without logging it as a turn action (status hooks, predefined bodies)."""
        return self._run(caster, self.program_for(text, source=source), battle, action)

    def _run(self, caster: "Character", program: Program, battle: "Battle", action: "ActionDef | None") -> ActionResult:
        result = ActionResult(action.id if action else "", caster.name)
        ctx = ExecutionContext(caster, battle, action, program, result)
        run_program(ctx)
        return result

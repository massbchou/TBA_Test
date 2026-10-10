"""Input providers decouple game logic from where player decisions come from.

- ConsoleInput: interactive play on stdin.
- ScriptedInput: a fixed list of answers, for tests.
- AutoInput: always picks the first option, for unattended demo runs.
"""
from __future__ import annotations

from typing import Protocol, Sequence


class InputProvider(Protocol):
    def choose(self, prompt: str, options: Sequence[str]) -> int:
        """Returns the 0-based index of the chosen option."""
        ...

    def ask_text(self, prompt: str, default: str) -> str:
        """Returns free text, or ``default`` when nothing is entered."""
        ...


class ConsoleInput:
    """Prompts on the console until a valid option number is entered."""

    def choose(self, prompt: str, options: Sequence[str]) -> int:
        if not options:
            raise ValueError("choose() requires at least one option")
        print(f"\n{prompt}")
        for i, opt in enumerate(options, start=1):
            print(f"  [{i}] {opt}")
        while True:
            try:
                raw = input("> ").strip()
            except EOFError:
                print("(no input, choosing option 1)")
                return 0
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                return int(raw) - 1
            print(f"Please enter a number between 1 and {len(options)}.")

    def ask_text(self, prompt: str, default: str) -> str:
        try:
            raw = input(f"\n{prompt} [{default}]: ").strip()
        except EOFError:
            return default
        return raw or default


class ScriptedInput:
    """Replays predetermined answers.

    Each answer is either a 0-based index or a string matched against the start of
    an option label (case-insensitive). Raises when it runs out of answers so tests
    fail loudly instead of hanging.
    """

    def __init__(self, answers: Sequence[int | str]):
        self.answers = list(answers)
        self.prompts: list[str] = []

    def choose(self, prompt: str, options: Sequence[str]) -> int:
        self.prompts.append(prompt)
        if not self.answers:
            raise RuntimeError(f"ScriptedInput ran out of answers at prompt: {prompt!r} {list(options)}")
        answer = self.answers.pop(0)
        if isinstance(answer, int):
            if not 0 <= answer < len(options):
                raise RuntimeError(f"Scripted answer {answer} out of range for {list(options)}")
            return answer
        for i, opt in enumerate(options):
            if opt.lower().startswith(answer.lower()):
                return i
        raise RuntimeError(f"Scripted answer {answer!r} matches none of {list(options)}")

    def ask_text(self, prompt: str, default: str) -> str:
        self.prompts.append(prompt)
        if self.answers and isinstance(self.answers[0], str) and self.answers[0].startswith("text:"):
            return self.answers.pop(0)[5:] or default
        return default


class AutoInput:
    """Always picks the first option and accepts every default."""

    def choose(self, prompt: str, options: Sequence[str]) -> int:
        return 0

    def ask_text(self, prompt: str, default: str) -> str:
        return default

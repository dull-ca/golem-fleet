import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

EXECUTABLE = "secretspec"
HELP_FLAGS = frozenset({"--help", "-h"})


def access_reason(program: str, argv: Sequence[str]) -> str:
    return " ".join([program, *argv])


def run_command(
    secretspec: str, program: str, module: str, argv: Sequence[str]
) -> list[str]:
    return [
        secretspec,
        "run",
        "--reason",
        access_reason(program, argv),
        "--",
        sys.executable,
        "-m",
        module,
        *argv,
    ]


def check_command(program: str) -> list[str]:
    return [
        EXECUTABLE,
        "check",
        "--explain",
        "--reason",
        access_reason(program, ()),
    ]


@dataclass(frozen=True)
class SecretsPolicy:
    required: tuple[str, ...]
    commands_running_without_secrets: frozenset[tuple[str, ...]] = frozenset()
    command_prefixes_running_without_secrets: frozenset[tuple[str, ...]] = frozenset()

    def are_resolved(self, environment: Mapping[str, str]) -> bool:
        return all(environment.get(name) for name in self.required)

    def needs_secrets(self, argv: Sequence[str]) -> bool:
        words = tuple(argv)
        if not words:
            return False
        if not HELP_FLAGS.isdisjoint(words):
            return False
        if words in self.commands_running_without_secrets:
            return False
        return not any(
            words[: len(prefix)] == prefix
            for prefix in self.command_prefixes_running_without_secrets
        )

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from golem_fleet.fault import Fault

MISSING_EXECUTABLE_EXIT_CODE = 127


class ExecutableNotFound(Fault):
    pass


class CommandFailed(Fault):
    pass


@dataclass(frozen=True)
class Completed:
    argv: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def raise_for_exit_code(self) -> Completed:
        if not self.ok:
            raise CommandFailed(self.argv, self.exit_code, self.stderr)
        return self


class Runner(Protocol):
    def capture(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        environment: Mapping[str, str] | None = None,
        stdin: str | bytes | None = None,
    ) -> Completed: ...

    def inherit(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        environment: Mapping[str, str] | None = None,
        stdin: str | bytes | None = None,
    ) -> int: ...

    def into_file(
        self,
        argv: Sequence[str],
        destination: Path,
        *,
        cwd: Path | None = None,
        environment: Mapping[str, str] | None = None,
        stdin: str | bytes | None = None,
    ) -> int: ...

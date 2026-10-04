from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from golem_fleet.fault import Fault

POLL_SECONDS = 10
RESET = "\x1b[0m"
DIM = "\x1b[2m"
GREEN = "\x1b[32m"
RED = "\x1b[31m"
YELLOW = "\x1b[33m"
CLEAR_LINE = "\x1b[2K"
DONE_STATUS = "done"
ERROR_STATUS = "error"
ERROR_INDENT = "    "
INSTALL_FAILED_EXIT_CODE = 1
INSTALL_FINISHED_EXIT_CODE = 0


@dataclass(frozen=True)
class StepPresentation:
    colour: str
    icon: str


UNRECOGNISED_PRESENTATION = StepPresentation(colour=DIM, icon="⬚")
STATUS_PRESENTATIONS = {
    DONE_STATUS: StepPresentation(colour=GREEN, icon="✅"),
    "doing": StepPresentation(colour=YELLOW, icon="⏳"),
    "todo": StepPresentation(colour=DIM, icon="⬚"),
    ERROR_STATUS: StepPresentation(colour=RED, icon="❌"),
}


class Progress(StrEnum):
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass(frozen=True)
class InstallStep:
    comment: str
    status: str
    error: str


class NotUnderstood(Fault):
    pass


class Source(Protocol):
    def get(self, path: str) -> object: ...


def path_for(service_name: str) -> str:
    return f"/dedicated/server/{service_name}/install/status"


def text_or(value: object, fallback: str) -> str:
    if value is None:
        return fallback
    return str(value)


def install_step(entry: object) -> InstallStep:
    if not isinstance(entry, Mapping):
        raise NotUnderstood(entry)
    return InstallStep(
        comment=text_or(entry.get("comment"), "(unnamed step)"),
        status=text_or(entry.get("status"), ""),
        error=text_or(entry.get("error"), ""),
    )


def parse(payload: object) -> tuple[InstallStep, ...]:
    if not isinstance(payload, Mapping):
        raise NotUnderstood(payload)
    progress = payload.get("progress")
    if progress is None:
        return ()
    if isinstance(progress, str) or not isinstance(progress, Sequence):
        raise NotUnderstood(progress)
    return tuple(install_step(entry) for entry in progress)


def step_lines(step: InstallStep) -> tuple[str, ...]:
    look = STATUS_PRESENTATIONS.get(step.status, UNRECOGNISED_PRESENTATION)
    headline = f"{look.colour}{look.icon} {step.comment}{RESET}"
    if not step.error:
        return (headline,)
    return (headline, f"{RED}{ERROR_INDENT}{step.error}{RESET}")


def status_lines(steps: Sequence[InstallStep]) -> tuple[str, ...]:
    return tuple(line for step in steps for line in step_lines(step))


def progress_of(steps: Sequence[InstallStep]) -> Progress:
    if any(step.status == ERROR_STATUS for step in steps):
        return Progress.ERROR
    if steps and all(step.status == DONE_STATUS for step in steps):
        return Progress.DONE
    return Progress.RUNNING


def redraw(drawn: int, lines: Sequence[str], write: Callable[[str], None]) -> int:
    if drawn:
        write(f"\x1b[{drawn}A")
    for line in lines:
        write(f"{CLEAR_LINE}{line}\n")
    return len(lines)


def follow(
    client: Source,
    service_name: str,
    *,
    write: Callable[[str], None],
    sleep: Callable[[float], None],
) -> int:
    status_path = path_for(service_name)
    drawn = 0
    while True:
        steps = parse(client.get(status_path))
        drawn = redraw(drawn, status_lines(steps), write)
        progress = progress_of(steps)
        if progress is Progress.ERROR:
            return INSTALL_FAILED_EXIT_CODE
        if progress is Progress.DONE:
            return INSTALL_FINISHED_EXIT_CODE
        sleep(POLL_SECONDS)

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from strabs.doit import RunConfig, doit, run

DEFAULT_MAX_WORKERS = 4


@dataclass(frozen=True)
class Work:
    name: str
    action: Callable[[], None]


@dataclass(frozen=True)
class Outcome:
    name: str
    ok: bool
    exit_code: int
    output: str


type ParallelWork = Callable[[Sequence[Work], int], Sequence[Outcome]]


def combined_output(stdout: str, stderr: str) -> str:
    return "\n".join(stream for stream in (stdout, stderr) if stream)


def doit_outcomes(work: Sequence[Work], max_workers: int) -> tuple[Outcome, ...]:
    config = RunConfig(
        max_workers=max_workers,
        fail_fast=False,
        raise_on_failure=False,
    )
    executed = doit([run(item.name, item.action) for item in work], config)
    return tuple(
        Outcome(
            name=task.name,
            ok=task.ok,
            exit_code=task.exit_code,
            output=combined_output(task.stdout, task.stderr),
        )
        for task in executed
    )


def run_in_parallel(
    work: Sequence[Work],
    *,
    max_workers: int = DEFAULT_MAX_WORKERS,
    executor: ParallelWork = doit_outcomes,
) -> tuple[Outcome, ...]:
    if not work:
        return ()
    outcomes = {outcome.name: outcome for outcome in executor(work, max_workers)}
    return tuple(outcomes[item.name] for item in work)

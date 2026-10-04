from collections.abc import Sequence
from dataclasses import dataclass, field

from golem_fleet.execution import tasks

FAILING_EXIT_CODE = 2


def do_nothing() -> None:
    return


def outcome_of(name: str, *, ok: bool = True) -> tasks.Outcome:
    exit_code = 0 if ok else FAILING_EXIT_CODE
    return tasks.Outcome(name=name, ok=ok, exit_code=exit_code, output=f"{name} spoke")


def work_named(*names: str) -> tuple[tasks.Work, ...]:
    return tuple(tasks.Work(name=name, action=do_nothing) for name in names)


@dataclass
class ReversingExecutor:
    outcomes: dict[str, tasks.Outcome] = field(default_factory=dict)
    seen_work: tuple[str, ...] = ()
    seen_max_workers: int = 0
    times_executed: int = 0

    def __call__(
        self, work: Sequence[tasks.Work], max_workers: int
    ) -> Sequence[tasks.Outcome]:
        self.seen_work = tuple(item.name for item in work)
        self.seen_max_workers = max_workers
        self.times_executed += 1
        return [self.outcomes.get(item.name, outcome_of(item.name)) for item in work][
            ::-1
        ]


def test_empty_work_returns_an_empty_tuple_without_reaching_the_executor() -> None:
    executor = ReversingExecutor()

    assert tasks.run_in_parallel((), executor=executor) == ()
    assert executor.times_executed == 0


def test_outcomes_follow_the_input_order_and_carry_the_failures_beside_them() -> None:
    unreachable = outcome_of("golem-two", ok=False)
    executor = ReversingExecutor({"golem-two": unreachable})

    outcomes = tasks.run_in_parallel(
        work_named("golem-one", "golem-two", "golem-three"),
        max_workers=9,
        executor=executor,
    )

    assert executor.seen_work == ("golem-one", "golem-two", "golem-three")
    assert executor.seen_max_workers == 9
    assert outcomes == (outcome_of("golem-one"), unreachable, outcome_of("golem-three"))


def test_the_output_of_an_outcome_joins_the_streams_that_spoke() -> None:
    assert tasks.combined_output("ran", "unreachable") == "ran\nunreachable"
    assert tasks.combined_output("", "unreachable") == "unreachable"
    assert tasks.combined_output("ran", "") == "ran"

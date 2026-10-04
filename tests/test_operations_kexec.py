from fake import RecordingRunner

from golem_fleet.operations import kexec

ADDRESS = "203.0.113.7"
LOAD_FAILED_EXIT_CODE = 7
DROPPED_SESSION_EXIT_CODE = 255
LOAD_ARGV = ("ssh", f"root@{ADDRESS}", kexec.LOAD_SCRIPT)
ENTER_ARGV = ("ssh", f"root@{ADDRESS}", kexec.ENTER_SCRIPT)


def runner_answering(
    *,
    load_exit_code: int = 0,
    enter_exit_code: int = 0,
) -> RecordingRunner:
    return (
        RecordingRunner()
        .responds_to(LOAD_ARGV, exit_code=load_exit_code)
        .responds_to(ENTER_ARGV, exit_code=enter_exit_code)
    )


def test_kexec_loads_the_kernel_on_the_host_before_entering_it() -> None:
    runner = runner_answering()
    entered: list[str] = []

    exit_code = kexec.enter(
        runner, ADDRESS, before_entering=lambda: entered.append(ADDRESS)
    )

    assert exit_code == 0
    assert [call.argv for call in runner.calls] == [LOAD_ARGV, ENTER_ARGV]
    assert entered == [ADDRESS]


def test_kexec_stops_without_entering_when_the_kernel_will_not_load() -> None:
    runner = runner_answering(load_exit_code=LOAD_FAILED_EXIT_CODE)
    entered: list[str] = []

    exit_code = kexec.enter(
        runner, ADDRESS, before_entering=lambda: entered.append(ADDRESS)
    )

    assert exit_code == LOAD_FAILED_EXIT_CODE
    assert [call.argv for call in runner.calls] == [LOAD_ARGV]
    assert entered == []


def test_kexec_succeeds_even_though_entering_the_kernel_drops_the_session() -> None:
    runner = runner_answering(enter_exit_code=DROPPED_SESSION_EXIT_CODE)

    assert kexec.enter(runner, ADDRESS, before_entering=lambda: None) == 0

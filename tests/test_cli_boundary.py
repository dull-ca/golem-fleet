import pytest

from golem_fleet.cli import boundary
from golem_fleet.execution import ports
from golem_fleet.fault import Fault

MISSING_EXECUTABLE_NAME = "golemctl"


class DeliberateFault(Fault):
    pass


REPORTED_FAULTS = [
    (DeliberateFault(MISSING_EXECUTABLE_NAME), boundary.COMMAND_FAULT_EXIT_CODE),
    (
        ports.ExecutableNotFound(MISSING_EXECUTABLE_NAME),
        ports.MISSING_EXECUTABLE_EXIT_CODE,
    ),
]


@pytest.mark.parametrize(("fault", "expected_exit_code"), REPORTED_FAULTS)
def test_a_named_fault_is_reported_on_stderr_and_carries_its_own_exit_code(
    capsys: pytest.CaptureFixture[str], fault: Exception, expected_exit_code: int
) -> None:
    def raise_the_fault() -> int:
        raise fault

    exit_code = boundary.command_exit_code(raise_the_fault)

    reported = capsys.readouterr().err
    assert exit_code == expected_exit_code
    assert type(fault).__name__ in reported
    assert MISSING_EXECUTABLE_NAME in reported


def test_a_standard_library_failure_is_left_to_surface_as_a_defect() -> None:
    def raise_a_defect() -> int:
        raise ValueError(MISSING_EXECUTABLE_NAME)

    with pytest.raises(ValueError, match=MISSING_EXECUTABLE_NAME):
        boundary.command_exit_code(raise_a_defect)

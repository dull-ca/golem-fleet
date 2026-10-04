from collections.abc import Callable
from typing import NoReturn

import typer

from golem_fleet.execution import ports
from golem_fleet.fault import Fault

COMMAND_SUCCEEDED_EXIT_CODE = 0
COMMAND_FAULT_EXIT_CODE = 1


def write_fault(fault: Exception) -> None:
    typer.echo(f"{type(fault).__name__}: {fault}", err=True)


def command_exit_code(action: Callable[[], int]) -> int:
    try:
        return action()
    except ports.ExecutableNotFound as missing:
        write_fault(missing)
        return ports.MISSING_EXECUTABLE_EXIT_CODE
    except Fault as fault:
        write_fault(fault)
        return COMMAND_FAULT_EXIT_CODE


def finished(action: Callable[[], int]) -> NoReturn:
    raise typer.Exit(code=command_exit_code(action))

import os
import shutil
import sys
from collections.abc import Mapping, Sequence

import typer

from golem_fleet.cli import application, boundary
from golem_fleet.cli.program import FleetProgram
from golem_fleet.execution import ports
from golem_fleet.fault import Fault
from golem_fleet.secrets import secretspec


class EntryModuleNotDeclared(Fault):
    pass


def secretspec_reexec_command(
    program: FleetProgram,
    argv: Sequence[str],
    environment: Mapping[str, str],
) -> list[str] | None:
    policy = program.secrets
    if policy is None or not policy.needs_secrets(argv):
        return None
    if policy.are_resolved(environment):
        return None
    if program.entry_module is None:
        raise EntryModuleNotDeclared(program.program_name)
    return secretspec.run_command(
        secretspec.EXECUTABLE,
        program.program_name,
        program.entry_module,
        argv,
    )


def replace_this_process_with(command: Sequence[str]) -> int:
    executable = shutil.which(command[0])
    if executable is None:
        raise ports.ExecutableNotFound(command[0])
    os.execv(executable, list(command))


def run(program: FleetProgram, app: typer.Typer) -> None:
    command = secretspec_reexec_command(program, sys.argv[1:], os.environ)
    if command is not None:
        raise SystemExit(
            boundary.command_exit_code(lambda: replace_this_process_with(command))
        )
    app(prog_name=program.program_name)


def main(program: FleetProgram, *, runner: ports.Runner | None = None) -> None:
    run(program, application.build(program, runner=runner))

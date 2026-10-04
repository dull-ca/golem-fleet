import os
from collections.abc import Mapping
from typing import Annotated

import typer

from golem_fleet.addresses import pulumi_stack
from golem_fleet.cli import boundary
from golem_fleet.cli.program import FleetProgram
from golem_fleet.execution import ports
from golem_fleet.fault import Fault
from golem_fleet.secrets import refresh, secretspec

SECRETSPEC_SET_SUBCOMMAND = "set"
CHECK_ONLY_FLAG = "--check"


class NoSecretEntriesDeclared(Fault):
    pass


def secret_entries_of(program: FleetProgram) -> Mapping[str, refresh.SecretEntry]:
    if not program.secret_entries:
        raise NoSecretEntriesDeclared
    return program.secret_entries


def run_secrets_check(program: FleetProgram, runner: ports.Runner) -> int:
    return runner.inherit(secretspec.check_command(program.program_name))


def stored_secret(runner: ports.Runner, entry: str, value: str) -> None:
    runner.capture(
        [secretspec.EXECUTABLE, SECRETSPEC_SET_SUBCOMMAND, entry],
        stdin=value,
    ).raise_for_exit_code()


def refresh_secrets(
    program: FleetProgram,
    runner: ports.Runner,
    *,
    checking_only: bool,
) -> int:
    entries = secret_entries_of(program)
    outputs = pulumi_stack.read(runner, stack=program.stack)
    comparisons = refresh.compare_secrets(outputs, os.environ, entries)
    if checking_only:
        return refresh.check_exit_code(comparisons, typer.echo)
    return refresh.store_secrets(
        comparisons,
        outputs,
        lambda entry, value: stored_secret(runner, entry, value),
        typer.echo,
    )


def build(program: FleetProgram, runner: ports.Runner) -> typer.Typer:
    app = typer.Typer(
        no_args_is_help=True,
        add_completion=False,
        help="Check the secrets this fleet needs, and refresh them.",
    )

    @app.command(name="check", help="Ask secretspec whether every secret resolves.")
    def check() -> None:
        boundary.finished(lambda: run_secrets_check(program, runner))

    @app.command(name="refresh", help="Write the secrets the stack minted back.")
    def refresh(
        *,
        checking_only: Annotated[
            bool,
            typer.Option(CHECK_ONLY_FLAG, help="Report differences, write nothing."),
        ] = False,
    ) -> None:
        boundary.finished(
            lambda: refresh_secrets(program, runner, checking_only=checking_only)
        )

    return app

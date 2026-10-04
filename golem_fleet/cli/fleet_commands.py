import os
from collections.abc import Mapping
from pathlib import Path

import typer

from golem_fleet.addresses import pulumi_stack, source
from golem_fleet.cli import boundary
from golem_fleet.cli.program import (
    ENVIRONMENT_SECRET_PROVIDER,
    FLEET_SUBCOMMAND,
    GOLEMCTL_EXECUTABLE,
    INVENTORY_FLAG,
    SECRET_PROVIDER_VARIABLE,
    FleetProgram,
)
from golem_fleet.execution import ports
from golem_fleet.fault import Fault
from golem_fleet.outputs import files
from golem_fleet.secrets import keys, registry_auth

PLAN_VERB = "plan"
APPLY_VERB = "apply"
STATUS_VERB = "status"
VERBS_CARRYING_THE_MANIFEST = (PLAN_VERB, APPLY_VERB)


class FleetKeyNotInTheEnvironment(Fault):
    pass


def golemctl_fleet_argv(program: FleetProgram, verb: str) -> list[str]:
    manifest = [str(program.manifest)] if verb in VERBS_CARRYING_THE_MANIFEST else []
    driven = [GOLEMCTL_EXECUTABLE, FLEET_SUBCOMMAND, verb]
    return [*driven, *manifest, INVENTORY_FLAG, str(program.inventory)]


def fleet_key_in(environment: Mapping[str, str]) -> keys.FleetKey:
    declared = environment.get(keys.ENVIRONMENT_VARIABLE, "")
    if not declared:
        raise FleetKeyNotInTheEnvironment(keys.ENVIRONMENT_VARIABLE)
    return keys.FleetKey(declared)


def registry_auth_variables(
    program: FleetProgram,
    runner: ports.Runner,
) -> dict[str, str]:
    host = program.registry_host
    variable = program.registry_auth_variable
    output = program.pull_credentials_output
    if host is None or variable is None or output is None:
        return {}
    exported = pulumi_stack.read(runner, stack=program.stack)
    return {variable: registry_auth.pull_auth(exported.get(output), registry_host=host)}


def golemctl_environment(
    program: FleetProgram,
    runner: ports.Runner,
    key_file: Path,
) -> dict[str, str]:
    return {
        keys.FILE_ENVIRONMENT_VARIABLE: str(key_file),
        SECRET_PROVIDER_VARIABLE: ENVIRONMENT_SECRET_PROVIDER,
        **registry_auth_variables(program, runner),
    }


def rendered_paths(program: FleetProgram, runner: ports.Runner) -> tuple[Path, ...]:
    resolved = source.resolve_all(program.addresses, runner)
    return files.write_all(
        program.fleet, resolved, declared=program.artifacts, into=program.generated
    )


def drive_golemctl(program: FleetProgram, runner: ports.Runner, verb: str) -> int:
    rendered_paths(program, runner)
    key = fleet_key_in(os.environ)
    with keys.materialised(key) as key_file:
        return runner.inherit(
            golemctl_fleet_argv(program, verb),
            environment=golemctl_environment(program, runner, key_file),
        )


def print_rendered_paths(program: FleetProgram, runner: ports.Runner) -> int:
    for path in rendered_paths(program, runner):
        typer.echo(str(path))
    return boundary.COMMAND_SUCCEEDED_EXIT_CODE


def build(program: FleetProgram, runner: ports.Runner) -> typer.Typer:
    app = typer.Typer(
        no_args_is_help=True,
        add_completion=False,
        help="Render the fleet and drive golemctl over it.",
    )

    @app.command(name=PLAN_VERB, help="Show what golemctl would change.")
    def plan() -> None:
        boundary.finished(lambda: drive_golemctl(program, runner, PLAN_VERB))

    @app.command(name=APPLY_VERB, help="Apply the fleet to every machine.")
    def apply() -> None:
        boundary.finished(lambda: drive_golemctl(program, runner, APPLY_VERB))

    @app.command(name=STATUS_VERB, help="Report what each machine is running.")
    def status() -> None:
        boundary.finished(lambda: drive_golemctl(program, runner, STATUS_VERB))

    @app.command(
        name="render", help="Write every generated artifact and print its path."
    )
    def render() -> None:
        boundary.finished(lambda: print_rendered_paths(program, runner))

    return app

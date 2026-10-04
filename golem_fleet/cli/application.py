from collections.abc import Callable

import typer
from typer._click import Command, Context
from typer.core import TyperGroup

from golem_fleet.cli import (
    boundary,
    fleet_commands,
    machine_commands,
    ovh_commands,
    placement_commands,
    secrets_commands,
)
from golem_fleet.cli.program import FleetProgram
from golem_fleet.execution import ports, process

FLEET_GROUP_NAME = "fleet"
MACHINE_GROUP_NAME = "machine"
PLACEMENT_GROUP_NAME = "placement"
SECRETS_GROUP_NAME = "secrets"
OVH_GROUP_NAME = "ovh"
PASSTHROUGH_COMMAND_NAME = "passthrough"

type GroupBuilder = Callable[[FleetProgram, ports.Runner], typer.Typer]

GROUP_BUILDERS: tuple[tuple[str, GroupBuilder], ...] = (
    (FLEET_GROUP_NAME, fleet_commands.build),
    (MACHINE_GROUP_NAME, machine_commands.build),
    (PLACEMENT_GROUP_NAME, placement_commands.build),
    (SECRETS_GROUP_NAME, secrets_commands.build),
)
PASSTHROUGH_CONTEXT_SETTINGS = {
    "allow_extra_args": True,
    "ignore_unknown_options": True,
    "allow_interspersed_args": False,
}


class PassthroughGroup(TyperGroup):
    def resolve_command(
        self,
        ctx: Context,
        args: list[str],
    ) -> tuple[str | None, Command | None, list[str]]:
        forwarding = self.commands.get(PASSTHROUGH_COMMAND_NAME)
        if args and forwarding is not None and args[0] not in self.commands:
            return PASSTHROUGH_COMMAND_NAME, forwarding, list(args)
        return super().resolve_command(ctx, args)


def ovh_commands_belong_in(program: FleetProgram) -> bool:
    return bool(program.ovh_endpoint_variable) and program.fleet.carries_ovh_bare_metal


def register_passthrough(
    app: typer.Typer,
    runner: ports.Runner,
    passthrough: str,
) -> None:
    @app.command(
        name=PASSTHROUGH_COMMAND_NAME,
        hidden=True,
        context_settings=PASSTHROUGH_CONTEXT_SETTINGS,
        help=f"Hand an unknown command to {passthrough}.",
    )
    def forward(context: typer.Context) -> None:
        boundary.finished(lambda: runner.inherit([passthrough, *context.args]))


def build(program: FleetProgram, *, runner: ports.Runner | None = None) -> typer.Typer:
    execution_runner = process.Runner() if runner is None else runner
    app = typer.Typer(
        name=program.program_name,
        cls=PassthroughGroup,
        no_args_is_help=True,
        add_completion=False,
        help=program.help_text,
    )

    for name, build_group in GROUP_BUILDERS:
        app.add_typer(build_group(program, execution_runner), name=name)
    if ovh_commands_belong_in(program):
        app.add_typer(ovh_commands.build(program), name=OVH_GROUP_NAME)

    if program.passthrough is not None:
        register_passthrough(app, execution_runner, program.passthrough)

    return app

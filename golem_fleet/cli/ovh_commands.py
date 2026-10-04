import json
import os
from typing import Annotated

import typer

from golem_fleet.cli import boundary, machine_commands
from golem_fleet.cli.program import FleetProgram
from golem_fleet.providers.ovh import api

OVH_COMMANDS_HELP = "Read the OVH API with the fleet's credentials."
JSON_INDENT = 2


def print_ovh_resource(
    program: FleetProgram,
    transport: api.Transport,
    api_path: str,
) -> int:
    client = api.Client(
        machine_commands.ovh_credentials_in(program, os.environ), transport
    )
    typer.echo(json.dumps(client.get(api_path), indent=JSON_INDENT, sort_keys=True))
    return boundary.COMMAND_SUCCEEDED_EXIT_CODE


def build(
    program: FleetProgram,
    *,
    transport: api.Transport | None = None,
) -> typer.Typer:
    app = typer.Typer(
        no_args_is_help=True,
        add_completion=False,
        help=OVH_COMMANDS_HELP,
    )
    ovh_transport = api.UrllibTransport() if transport is None else transport

    @app.callback(help=OVH_COMMANDS_HELP)
    def ovh() -> None:
        return

    @app.command(name="get", help="Print the OVH API answer as indented JSON.")
    def get(
        api_path: Annotated[
            str,
            typer.Argument(help="OVH API path, such as /dedicated/server."),
        ],
    ) -> None:
        boundary.finished(lambda: print_ovh_resource(program, ovh_transport, api_path))

    return app

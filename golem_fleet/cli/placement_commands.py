import typer

from golem_fleet.addresses import source
from golem_fleet.cli import boundary
from golem_fleet.cli.program import FleetProgram
from golem_fleet.execution import ports
from golem_fleet.fleet import components, hostnames, machines

PLACEMENT_COMMANDS_HELP = "Show what runs where, with every machine's address."
MACHINE_NAME_WIDTH = 8
COMPONENT_NAME_WIDTH = 16
COMPONENT_INDENT = "  "
NOT_DEPLOYED = "not deployed"
INTERNAL_ANSWERING = "internal"


def machine_heading(machine: machines.Machine, addresses: source.Addresses) -> str:
    resolved = addresses.get(machine.name)
    address = NOT_DEPLOYED if resolved is None else resolved.ipv4
    return f"{machine.name:<{MACHINE_NAME_WIDTH}} {address}"


def component_answering(component: components.Component) -> str:
    if isinstance(component.answering, hostnames.Internal):
        return INTERNAL_ANSWERING
    return ", ".join(hostname.text for hostname in component.hostnames)


def component_line(component: components.Component) -> str:
    name = f"{component.name:<{COMPONENT_NAME_WIDTH}}"
    return f"{COMPONENT_INDENT}{name} {component_answering(component)}"


def placement_lines(
    program: FleetProgram, addresses: source.Addresses
) -> tuple[str, ...]:
    blocks = [
        (
            machine_heading(machine, addresses),
            *(
                component_line(component)
                for component in program.fleet.components_by_machine[machine.name]
            ),
        )
        for machine in program.fleet.machines
    ]
    lines: list[str] = []
    for position, block in enumerate(blocks):
        if position:
            lines.append("")
        lines.extend(block)
    return tuple(lines)


def resolved_or_undeployed(
    program: FleetProgram, runner: ports.Runner
) -> source.Addresses:
    try:
        return source.resolve_all(program.addresses, runner)
    except source.Unavailable as unavailable:
        boundary.write_fault(unavailable)
        return {}


def print_placement(program: FleetProgram, runner: ports.Runner) -> int:
    addresses = resolved_or_undeployed(program, runner)
    for line in placement_lines(program, addresses):
        typer.echo(line)
    return boundary.COMMAND_SUCCEEDED_EXIT_CODE


def build(program: FleetProgram, runner: ports.Runner) -> typer.Typer:
    app = typer.Typer(add_completion=False, help=PLACEMENT_COMMANDS_HELP)

    @app.callback(invoke_without_command=True, help=PLACEMENT_COMMANDS_HELP)
    def show() -> None:
        boundary.finished(lambda: print_placement(program, runner))

    return app

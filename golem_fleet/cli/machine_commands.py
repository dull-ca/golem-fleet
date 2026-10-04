import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from golem_fleet.addresses import source
from golem_fleet.cli import boundary
from golem_fleet.cli.program import FleetProgram
from golem_fleet.execution import ports, tasks
from golem_fleet.fault import Fault
from golem_fleet.fleet import machines, placements
from golem_fleet.operations import agent, diagnostics, kexec
from golem_fleet.outputs import cloud_config
from golem_fleet.providers.ovh import api, baremetal, install_status
from golem_fleet.secrets import keys

FIELD_SEPARATOR = "\t"
OVH_APPLICATION_KEY_VARIABLE = "OVH_APPLICATION_KEY"
OVH_APPLICATION_SECRET_VARIABLE = "OVH_APPLICATION_SECRET"
OVH_CONSUMER_KEY_VARIABLE = "OVH_CONSUMER_KEY"
EVERY_MACHINE_FLAG = "--all"
SSH_KEY_OPTION = "--ssh-key"
GOLEM_AUTH_TOKEN_VARIABLE = "GOLEM_AUTH_TOKEN"
MACHINE_ARGUMENT_HELP = "Machine to act on."
FAILURE_OUTPUT_INDENT = "  "


class MachineIsNotOvhBareMetal(Fault):
    pass


class GolemCredentialVariableNotSet(Fault):
    pass


class MachineAnswersOnIpv4Only(Fault):
    pass


class AgentBinaryVariableNotSet(Fault):
    pass


class SshPublicKeyNotFound(Fault):
    pass


class NoMachineToActOn(Fault):
    pass


class MachineActionFailed(Fault):
    pass


@dataclass(frozen=True)
class MachineCommandContext:
    program: FleetProgram
    runner: ports.Runner
    transport: api.Transport
    sleep: Callable[[float], None]


type NamedMachineAction = Callable[[MachineCommandContext, str], int]

type FanoutActionBuilder = Callable[[MachineCommandContext], Callable[[str, str], int]]


def ovh_service_name(fleet: placements.Fleet, machine_name: str) -> str:
    machine = fleet.machine_named(machine_name)
    if machine.ovh is None:
        raise MachineIsNotOvhBareMetal(machine_name)
    return machine.ovh.service_name


def machine_line(machine: machines.Machine) -> str:
    if machine.ovh is None:
        return machine.name
    return f"{machine.name}{FIELD_SEPARATOR}{machine.ovh.service_name}"


def print_machine_lines(fleet: placements.Fleet) -> int:
    for machine in fleet.machines:
        typer.echo(machine_line(machine))
    return boundary.COMMAND_SUCCEEDED_EXIT_CODE


def machine_addresses(ctx: MachineCommandContext, name: str) -> source.MachineAddresses:
    ctx.program.fleet.machine_named(name)
    resolved = source.resolve_all(ctx.program.addresses, ctx.runner)
    return source.for_machine(resolved, name)


def print_ipv4(context: MachineCommandContext, machine_name: str) -> int:
    typer.echo(machine_addresses(context, machine_name).ipv4)
    return boundary.COMMAND_SUCCEEDED_EXIT_CODE


def print_ipv6(context: MachineCommandContext, machine_name: str) -> int:
    ipv6 = machine_addresses(context, machine_name).ipv6
    if ipv6 is None:
        raise MachineAnswersOnIpv4Only(machine_name)
    typer.echo(ipv6)
    return boundary.COMMAND_SUCCEEDED_EXIT_CODE


def declared_credential_in(environment: Mapping[str, str], variable: str) -> str:
    declared = environment.get(variable, "")
    if not declared:
        raise GolemCredentialVariableNotSet(variable)
    return declared


def golem_credentials_in(
    environment: Mapping[str, str],
) -> cloud_config.Credentials:
    auth_token = declared_credential_in(environment, GOLEM_AUTH_TOKEN_VARIABLE)
    fleet_key = keys.FleetKey(
        declared_credential_in(environment, keys.ENVIRONMENT_VARIABLE)
    )
    return cloud_config.Credentials(auth_token=auth_token, secret_key=fleet_key.value)


def reinstall_policy_of(machine: machines.Machine) -> machines.ReinstallPolicy:
    if machine.ovh is None:
        return machines.ProtectedFromReinstall()
    return machine.ovh.reinstall


def print_cloud_config(context: MachineCommandContext, machine_name: str) -> int:
    machine = context.program.fleet.machine_named(machine_name)
    credentials = golem_credentials_in(os.environ)
    typer.echo(
        cloud_config.render(credentials, reinstall_policy_of(machine)),
        nl=False,
    )
    return boundary.COMMAND_SUCCEEDED_EXIT_CODE


def ovh_credentials_in(
    program: FleetProgram,
    environment: Mapping[str, str],
) -> api.Credentials:
    return api.Credentials(
        endpoint=environment.get(program.ovh_endpoint_variable, ""),
        application_key=environment.get(OVH_APPLICATION_KEY_VARIABLE, ""),
        application_secret=environment.get(OVH_APPLICATION_SECRET_VARIABLE, ""),
        consumer_key=environment.get(OVH_CONSUMER_KEY_VARIABLE, ""),
    )


def agent_binary_in(program: FleetProgram, environment: Mapping[str, str]) -> Path:
    declared = environment.get(program.agent_binary_variable, "")
    if not declared:
        raise AgentBinaryVariableNotSet(program.agent_binary_variable)
    return Path(declared)


def ssh_public_key_in(key_path: Path) -> str:
    if not key_path.is_file():
        raise SshPublicKeyNotFound(key_path)
    return key_path.read_text(encoding="utf-8")


def write_progress(text: str) -> None:
    typer.echo(text, nl=False)


def outcome_summary(outcome: tasks.Outcome) -> str:
    state = "ok" if outcome.ok else f"failed ({outcome.exit_code})"
    return f"{outcome.name}{FIELD_SEPARATOR}{state}"


def machine_work(
    action: Callable[[str, str], int],
    machine_name: str,
    addresses: source.Addresses,
) -> tasks.Work:
    def act() -> None:
        exit_code = action(
            machine_name, source.for_machine(addresses, machine_name).ipv4
        )
        if exit_code != boundary.COMMAND_SUCCEEDED_EXIT_CODE:
            raise MachineActionFailed(machine_name, exit_code)

    return tasks.Work(machine_name, act)


def report_outcome_output(outcome: tasks.Outcome) -> None:
    for line in outcome.output.splitlines():
        typer.echo(f"{FAILURE_OUTPUT_INDENT}{line}", err=True)


def act_on_every_machine(
    context: MachineCommandContext,
    action: Callable[[str, str], int],
) -> int:
    addresses = source.resolve_all(context.program.addresses, context.runner)
    machines = context.program.fleet.machines
    outcomes = tasks.run_in_parallel(
        tuple(machine_work(action, machine.name, addresses) for machine in machines)
    )
    for outcome in outcomes:
        typer.echo(outcome_summary(outcome))
        if not outcome.ok:
            report_outcome_output(outcome)
    if all(outcome.ok for outcome in outcomes):
        return boundary.COMMAND_SUCCEEDED_EXIT_CODE
    return boundary.COMMAND_FAULT_EXIT_CODE


def act_on_the_named_or_every_machine(
    context: MachineCommandContext,
    machine_name: str | None,
    action: Callable[[str, str], int],
    *,
    every_machine: bool,
) -> int:
    if every_machine:
        return act_on_every_machine(context, action)
    if machine_name is None:
        raise NoMachineToActOn(tuple(m.name for m in context.program.fleet.machines))
    return action(machine_name, machine_addresses(context, machine_name).ipv4)


def ovh_command(command: Callable[[ports.Runner, str], int]) -> NamedMachineAction:
    def ask_ovh(context: MachineCommandContext, machine_name: str) -> int:
        return command(
            context.runner,
            ovh_service_name(context.program.fleet, machine_name),
        )

    return ask_ovh


NO_INSTALL_IN_PROGRESS_EXIT_CODE = 0


def follow_ovh_install(context: MachineCommandContext, machine_name: str) -> int:
    credentials = ovh_credentials_in(context.program, os.environ)
    service_name = ovh_service_name(context.program.fleet, machine_name)
    client = api.Client(credentials, context.transport)
    try:
        return install_status.follow(
            client, service_name, write=write_progress, sleep=context.sleep
        )
    except api.ResourceNotFound:
        write_progress(machine_name)
        return NO_INSTALL_IN_PROGRESS_EXIT_CODE


def send_agent(context: MachineCommandContext, machine_name: str) -> int:
    binary = agent_binary_in(context.program, os.environ)
    address = machine_addresses(context, machine_name).ipv4
    return agent.install(context.runner, address, binary)


def open_serial_console(
    context: MachineCommandContext,
    machine_name: str,
    key_path: Path,
) -> int:
    return baremetal.console(
        context.runner,
        ovh_service_name(context.program.fleet, machine_name),
        ssh_public_key_in(key_path),
    )


def diagnose_machine(context: MachineCommandContext) -> Callable[[str, str], int]:
    def collect(machine_name: str, address: str) -> int:
        into = context.program.generated / "diagnostics"
        typer.echo(
            str(diagnostics.collect(context.runner, machine_name, address, into))
        )
        return boundary.COMMAND_SUCCEEDED_EXIT_CODE

    return collect


def report_agent_status(context: MachineCommandContext) -> Callable[[str, str], int]:
    def report(machine_name: str, address: str) -> int:
        del machine_name
        return agent.status(context.runner, address)

    return report


def kexec_machine(context: MachineCommandContext) -> Callable[[str, str], int]:
    def boot(machine_name: str, address: str) -> int:
        return kexec.enter(
            context.runner,
            address,
            before_entering=lambda: typer.echo(machine_name),
        )

    return boot


NAMED_MACHINE_COMMANDS: tuple[tuple[str, str, NamedMachineAction], ...] = (
    ("address", "Print the IPv4 address of one machine.", print_ipv4),
    ("address6", "Print the IPv6 address of one machine.", print_ipv6),
    ("cloud-config", "Print one machine's cloud-config.", print_cloud_config),
    ("agent", "Install a freshly built golemd.", send_agent),
)
OVH_MACHINE_COMMANDS: tuple[tuple[str, str, NamedMachineAction], ...] = (
    ("info", "Print what OVH knows about one server.", ovh_command(baremetal.info)),
    ("tasks", "List the OVH tasks on one machine.", ovh_command(baremetal.tasks)),
    ("interventions", "List OVH interventions.", ovh_command(baremetal.interventions)),
    ("kvm", "Open the OVH KVM-over-IP console.", ovh_command(baremetal.kvm)),
    ("rescue", "Reboot one OVH machine into rescue.", ovh_command(baremetal.rescue)),
    ("status", "Follow the OVH installation of one machine.", follow_ovh_install),
)
FANOUT_COMMANDS: tuple[tuple[str, str, FanoutActionBuilder], ...] = (
    ("kexec", "Boot into the running kernel again.", kexec_machine),
    ("diagnose", "Collect a diagnostics report.", diagnose_machine),
    ("agent-status", "Report what golemd is doing.", report_agent_status),
)


def register_named_machine_command(
    app: typer.Typer,
    context: MachineCommandContext,
    name: str,
    description: str,
    action: NamedMachineAction,
) -> None:
    @app.command(name=name, help=description)
    def act(
        machine_name: Annotated[str, typer.Argument(help=MACHINE_ARGUMENT_HELP)],
    ) -> None:
        boundary.finished(lambda: action(context, machine_name))


def register_fanout_command(
    app: typer.Typer,
    context: MachineCommandContext,
    name: str,
    description: str,
    action: Callable[[str, str], int],
) -> None:
    @app.command(name=name, help=description)
    def act(
        machine_name: Annotated[
            str | None,
            typer.Argument(help="Machine to act on, unless --all is given."),
        ] = None,
        *,
        every_machine: Annotated[
            bool,
            typer.Option(EVERY_MACHINE_FLAG, help="Act on every machine."),
        ] = False,
    ) -> None:
        boundary.finished(
            lambda: act_on_the_named_or_every_machine(
                context, machine_name, action, every_machine=every_machine
            )
        )


def register_machine_listing(app: typer.Typer, ctx: MachineCommandContext) -> None:
    @app.command(name="list", help="Print every machine and its service name.")
    def list_machines() -> None:
        boundary.finished(lambda: print_machine_lines(ctx.program.fleet))


def register_ovh_console(app: typer.Typer, ctx: MachineCommandContext) -> None:
    @app.command(name="console", help="Open a serial-over-LAN console.")
    def console(
        machine_name: Annotated[str, typer.Argument(help=MACHINE_ARGUMENT_HELP)],
        ssh_key: Annotated[
            Path,
            typer.Option(SSH_KEY_OPTION, help="Public key OVH installs."),
        ],
    ) -> None:
        boundary.finished(lambda: open_serial_console(ctx, machine_name, ssh_key))


def build(
    program: FleetProgram,
    runner: ports.Runner,
    *,
    transport: api.Transport | None = None,
    sleep: Callable[[float], None] | None = None,
) -> typer.Typer:
    app = typer.Typer(
        no_args_is_help=True,
        add_completion=False,
        help="Look at one machine, or act on every one.",
    )
    context = MachineCommandContext(
        program=program,
        runner=runner,
        transport=api.UrllibTransport() if transport is None else transport,
        sleep=time.sleep if sleep is None else sleep,
    )
    register_machine_listing(app, context)
    for name, description, action in NAMED_MACHINE_COMMANDS:
        register_named_machine_command(app, context, name, description, action)
    if program.fleet.carries_ovh_bare_metal:
        register_ovh_console(app, context)
        for name, description, action in OVH_MACHINE_COMMANDS:
            register_named_machine_command(app, context, name, description, action)
    for name, description, build_action in FANOUT_COMMANDS:
        register_fanout_command(app, context, name, description, build_action(context))
    return app

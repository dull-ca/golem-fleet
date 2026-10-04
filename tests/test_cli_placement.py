from conftest import (
    DOCS_COMPONENT,
    DOCS_HOSTNAME,
    INGRESS_COMPONENT,
    OVH_IPV4,
    OVH_MACHINE,
    SITE_CANONICAL,
    SITE_COMPONENT,
    SITE_REDIRECT,
    STATIC_MACHINE,
    fleet_program,
    only_the_ovh_address,
)
from fake import RecordingRunner
from typer.testing import CliRunner

from golem_fleet.addresses import source
from golem_fleet.cli import application, placement_commands
from golem_fleet.execution import ports

UNRESOLVED_STACK = "prod"
EXPECTED_DEPLOYED_TABLE = (
    f"{OVH_MACHINE}  {OVH_IPV4}",
    f"  {INGRESS_COMPONENT}          {placement_commands.INTERNAL_ANSWERING}",
    f"  {SITE_COMPONENT}     {SITE_CANONICAL}, {SITE_REDIRECT}",
    "",
    f"{STATIC_MACHINE}   {placement_commands.NOT_DEPLOYED}",
    f"  {DOCS_COMPONENT}       {DOCS_HOSTNAME}",
)


class UnresolvableAddresses:
    def resolve(self, runner: ports.Runner) -> source.Addresses:
        del runner
        raise source.Unavailable(UNRESOLVED_STACK)


def test_the_table_pads_the_names_and_lists_the_canonical_hostname_first() -> None:
    addresses = only_the_ovh_address()
    program = fleet_program(addresses=addresses)

    lines = placement_commands.placement_lines(
        program, source.resolve_all(addresses, RecordingRunner())
    )

    assert lines == EXPECTED_DEPLOYED_TABLE


def test_the_placement_command_is_reached_from_the_application() -> None:
    app = application.build(fleet_program(), runner=RecordingRunner())

    result = CliRunner().invoke(app, ["placement"])

    assert result.exit_code == 0
    assert OVH_MACHINE in result.stdout
    assert DOCS_HOSTNAME in result.stdout


def test_unresolvable_addresses_are_reported_and_the_placement_still_prints() -> None:
    program = fleet_program(addresses=(UnresolvableAddresses(),))
    app = placement_commands.build(program, RecordingRunner())

    result = CliRunner().invoke(app, [])

    assert result.exit_code == 0
    assert source.Unavailable.__name__ in result.stderr
    assert UNRESOLVED_STACK in result.stderr
    assert result.stdout.count(placement_commands.NOT_DEPLOYED) == 2
    assert SITE_CANONICAL in result.stdout

from pathlib import Path

from conftest import fleet_program, program_without_bare_metal
from fake import RecordingRunner
from typer.testing import CliRunner

from golem_fleet.cli import application
from golem_fleet.cli.program import FleetProgram

PASSTHROUGH_TOOL = "dulliac"
UNKNOWN_COMMAND = "up"
KNOWN_FLEET_COMMAND = "render"
NO_SUCH_COMMAND_EXIT_CODE = 2
CONSUMING_HELP = "Drive the strabs fleet. An unknown verb is handed to pulumi."
DEFAULT_HELP = "Drive the golem-fleet fleet."


def passthrough_runner() -> RecordingRunner:
    runner = RecordingRunner()
    return runner.responds_to_prefix([PASSTHROUGH_TOOL])


def command_names_of(program: FleetProgram) -> list[str]:
    app = application.build(program, runner=RecordingRunner())
    groups_and_commands = [*app.registered_groups, *app.registered_commands]
    return [info.name for info in groups_and_commands if info.name is not None]


def test_every_group_is_wired_in_and_ovh_only_when_the_fleet_has_bare_metal() -> None:
    names = command_names_of(fleet_program())

    assert application.FLEET_GROUP_NAME in names
    assert application.MACHINE_GROUP_NAME in names
    assert application.PLACEMENT_GROUP_NAME in names
    assert application.SECRETS_GROUP_NAME in names
    assert application.OVH_GROUP_NAME in names
    assert application.OVH_GROUP_NAME not in command_names_of(
        program_without_bare_metal()
    )


def test_an_unknown_command_reaches_the_passthrough_only_when_one_is_declared() -> None:
    runner = passthrough_runner()
    words = [UNKNOWN_COMMAND, "--yes", "-f"]
    declared = application.build(
        fleet_program(passthrough=PASSTHROUGH_TOOL), runner=runner
    )

    handed_over = CliRunner().invoke(declared, words)
    refused = CliRunner().invoke(
        application.build(fleet_program(), runner=runner), words
    )

    assert handed_over.exit_code == 0
    assert runner.last_call.argv == (PASSTHROUGH_TOOL, *words)
    assert refused.exit_code == NO_SUCH_COMMAND_EXIT_CODE


def test_a_known_command_is_never_handed_to_the_passthrough_tool(
    tmp_path: Path,
) -> None:
    runner = passthrough_runner()
    program = fleet_program(generated=tmp_path, passthrough=PASSTHROUGH_TOOL)

    result = CliRunner().invoke(
        application.build(program, runner=runner),
        [application.FLEET_GROUP_NAME, KNOWN_FLEET_COMMAND],
    )

    assert result.exit_code == 0
    assert runner.calls_to([PASSTHROUGH_TOOL]) == ()


def test_the_top_level_help_is_the_programs_own_whenever_it_declares_one() -> None:
    declared = application.build(
        fleet_program(help=CONSUMING_HELP), runner=RecordingRunner()
    )
    derived = application.build(fleet_program(), runner=RecordingRunner())

    assert declared.info.help == CONSUMING_HELP
    assert derived.info.help == DEFAULT_HELP

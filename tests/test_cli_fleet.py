import json
from pathlib import Path

import pytest
from conftest import (
    MALFORMED_FLEET_KEY,
    PLACEMENT_FILENAME,
    PULL_CREDENTIALS_OUTPUT,
    REGISTRY_AUTH_VARIABLE,
    REGISTRY_HOST,
    WELL_FORMED_FLEET_KEY,
    fleet_program,
)
from fake import RecordingRunner
from typer.testing import CliRunner, Result

from golem_fleet.cli import application, fleet_commands
from golem_fleet.cli.program import (
    ENVIRONMENT_SECRET_PROVIDER,
    FLEET_SUBCOMMAND,
    GOLEMCTL_EXECUTABLE,
    INVENTORY_FLAG,
    SECRET_PROVIDER_VARIABLE,
    FleetProgram,
)
from golem_fleet.execution import ports
from golem_fleet.outputs import files
from golem_fleet.secrets import keys

PULL_AUTH = "Z29sZW06cHVsbC10b2tlbg=="
DOCKER_CONFIG_JSON = json.dumps({"auths": {REGISTRY_HOST: {"auth": PULL_AUTH}}})
MANIFEST_PATH = "services/main.emet"
GOLEMCTL_PREFIX = (GOLEMCTL_EXECUTABLE, FLEET_SUBCOMMAND)
PULUMI_PREFIX = ("pulumi", "stack", "output")
KEY_FILE_NAME = "secret-key"
MANIFEST_WORDS_BY_VERB = [
    (fleet_commands.PLAN_VERB, [MANIFEST_PATH]),
    (fleet_commands.APPLY_VERB, [MANIFEST_PATH]),
    (fleet_commands.STATUS_VERB, []),
]
UNUSABLE_KEYS = [
    (None, fleet_commands.FleetKeyNotInTheEnvironment),
    (MALFORMED_FLEET_KEY, keys.WrongLength),
]


def golemctl_runner() -> RecordingRunner:
    runner = RecordingRunner()
    return runner.responds_to_prefix(list(GOLEMCTL_PREFIX))


def stack_output_runner() -> RecordingRunner:
    stack_output = json.dumps({PULL_CREDENTIALS_OUTPUT: DOCKER_CONFIG_JSON})
    runner = golemctl_runner()
    return runner.responds_to_prefix(list(PULUMI_PREFIX), stdout=stack_output)


def fleet_command(
    words: list[str], program: FleetProgram, runner: ports.Runner
) -> Result:
    return CliRunner().invoke(
        application.build(program, runner=runner), ["fleet", *words]
    )


@pytest.mark.parametrize(("verb", "manifest"), MANIFEST_WORDS_BY_VERB)
def test_every_verb_renders_the_fleet_then_runs_golemctl_with_its_own_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verb: str, manifest: list[str]
) -> None:
    monkeypatch.setenv(keys.ENVIRONMENT_VARIABLE, WELL_FORMED_FLEET_KEY)
    runner = golemctl_runner()

    result = fleet_command([verb], fleet_program(generated=tmp_path), runner)

    assert result.exit_code == 0
    assert (tmp_path / files.INVENTORY_FILENAME).is_file()
    assert runner.last_call.argv == (
        *GOLEMCTL_PREFIX,
        verb,
        *manifest,
        INVENTORY_FLAG,
        str(tmp_path / files.INVENTORY_FILENAME),
    )


def test_the_golemctl_environment_points_at_the_key_file_and_the_registry_auth(
    tmp_path: Path,
) -> None:
    key_file = tmp_path / KEY_FILE_NAME
    with_registry_declared = fleet_program(
        generated=tmp_path,
        registry_host=REGISTRY_HOST,
        registry_auth_variable=REGISTRY_AUTH_VARIABLE,
        pull_credentials_output=PULL_CREDENTIALS_OUTPUT,
    )

    without_registry = fleet_commands.golemctl_environment(
        fleet_program(generated=tmp_path), golemctl_runner(), key_file
    )
    with_registry = fleet_commands.golemctl_environment(
        with_registry_declared, stack_output_runner(), key_file
    )

    assert without_registry == {
        keys.FILE_ENVIRONMENT_VARIABLE: str(key_file),
        SECRET_PROVIDER_VARIABLE: ENVIRONMENT_SECRET_PROVIDER,
    }
    assert with_registry == {**without_registry, REGISTRY_AUTH_VARIABLE: PULL_AUTH}


def test_the_key_reaches_golemctl_only_as_a_file_that_is_removed_afterwards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(keys.ENVIRONMENT_VARIABLE, WELL_FORMED_FLEET_KEY)
    runner = golemctl_runner()
    program = fleet_program(generated=tmp_path)

    result = fleet_command([fleet_commands.APPLY_VERB], program, runner)

    environment = runner.last_call.environment
    assert environment is not None
    key_path = environment[keys.FILE_ENVIRONMENT_VARIABLE]
    assert key_path.endswith(KEY_FILE_NAME)
    assert not Path(key_path).exists()
    assert WELL_FORMED_FLEET_KEY not in result.output
    assert all(
        WELL_FORMED_FLEET_KEY not in word for call in runner.calls for word in call.argv
    )


@pytest.mark.parametrize(("declared", "expected_fault"), UNUSABLE_KEYS)
def test_a_key_golemctl_cannot_use_stops_the_command_before_golemctl_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    declared: str | None,
    expected_fault: type[Exception],
) -> None:
    if declared is None:
        monkeypatch.delenv(keys.ENVIRONMENT_VARIABLE, raising=False)
    else:
        monkeypatch.setenv(keys.ENVIRONMENT_VARIABLE, declared)
    runner = golemctl_runner()
    program = fleet_program(generated=tmp_path)

    result = fleet_command([fleet_commands.PLAN_VERB], program, runner)

    assert result.exit_code == 1
    assert expected_fault.__name__ in result.stderr
    assert MALFORMED_FLEET_KEY not in result.output
    assert runner.calls_to(list(GOLEMCTL_PREFIX)) == ()


def test_rendering_prints_the_path_of_every_file_it_wrote(tmp_path: Path) -> None:
    program = fleet_program(generated=tmp_path)
    runner = golemctl_runner()

    rendered = fleet_command(["render"], program, runner)

    assert rendered.exit_code == 0
    assert rendered.stdout.splitlines() == [
        str(tmp_path / files.INVENTORY_FILENAME),
        str(tmp_path / PLACEMENT_FILENAME),
    ]


def test_a_program_declaring_nothing_still_has_its_inventory_written(
    tmp_path: Path,
) -> None:
    program = fleet_program(generated=tmp_path, artifacts=())

    rendered = fleet_command(["render"], program, golemctl_runner())

    assert rendered.exit_code == 0
    assert rendered.stdout.splitlines() == [str(tmp_path / files.INVENTORY_FILENAME)]

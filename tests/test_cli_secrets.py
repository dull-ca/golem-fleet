import json

import pytest
from conftest import fleet_program
from fake import RecordingRunner
from typer.testing import CliRunner, Result

from golem_fleet.cli import secrets_commands
from golem_fleet.secrets import refresh, secretspec

MINTED_OUTPUT_NAME = "databasePassword"
SECRETSPEC_ENTRY = "DATABASE_PASSWORD"
MINTED_SECRET_VALUE = "a-minted-secret-nobody-should-print"
STALE_SECRET_VALUE = "the-old-secret"
SECRET_ENTRIES = {MINTED_OUTPUT_NAME: SECRETSPEC_ENTRY}
PULUMI_PREFIX = ["pulumi", "stack", "output"]
SECRETSPEC = secretspec.EXECUTABLE
SECRETSPEC_SET_PREFIX = [SECRETSPEC, secrets_commands.SECRETSPEC_SET_SUBCOMMAND]


def secrets_runner() -> RecordingRunner:
    minted = json.dumps({MINTED_OUTPUT_NAME: MINTED_SECRET_VALUE})
    runner = RecordingRunner().responds_to_prefix([SECRETSPEC])
    return runner.responds_to_prefix(PULUMI_PREFIX, stdout=minted)


def secrets_command(words: list[str], runner: RecordingRunner) -> Result:
    program = fleet_program(secret_entries=SECRET_ENTRIES)
    return CliRunner().invoke(secrets_commands.build(program, runner), words)


def test_check_runs_the_secretspec_check_command() -> None:
    runner = secrets_runner()
    program = fleet_program()

    result = CliRunner().invoke(secrets_commands.build(program, runner), ["check"])

    assert result.exit_code == 0
    assert runner.last_call.argv[:3] == (SECRETSPEC, "check", "--explain")
    assert program.program_name in runner.last_call.argv[-1]


def test_refresh_without_a_mapping_refuses_to_run() -> None:
    with pytest.raises(secrets_commands.NoSecretEntriesDeclared):
        secrets_commands.refresh_secrets(
            fleet_program(), secrets_runner(), checking_only=True
        )


def test_refresh_checking_only_exits_zero_when_the_secret_already_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(SECRETSPEC_ENTRY, MINTED_SECRET_VALUE)
    program = fleet_program(secret_entries=SECRET_ENTRIES)

    exit_code = secrets_commands.refresh_secrets(
        program, secrets_runner(), checking_only=True
    )

    assert exit_code == refresh.SECRETS_MATCH_EXIT_CODE


def test_refresh_stores_the_differing_secret_unless_only_checking_and_prints_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(SECRETSPEC_ENTRY, STALE_SECRET_VALUE)
    checking_runner = secrets_runner()
    storing_runner = secrets_runner()

    checked = secrets_command(["refresh", "--check"], checking_runner)
    stored = secrets_command(["refresh"], storing_runner)

    assert checked.exit_code == refresh.SECRETS_DIFFER_EXIT_CODE
    assert checking_runner.calls_to(SECRETSPEC_SET_PREFIX) == ()
    assert stored.exit_code == 0
    written = storing_runner.calls_to(SECRETSPEC_SET_PREFIX)[0]
    assert written.argv == (*SECRETSPEC_SET_PREFIX, SECRETSPEC_ENTRY)
    assert written.stdin == MINTED_SECRET_VALUE
    assert SECRETSPEC_ENTRY in stored.stdout
    for output in (checked.output, stored.output):
        assert MINTED_SECRET_VALUE not in output
        assert STALE_SECRET_VALUE not in output

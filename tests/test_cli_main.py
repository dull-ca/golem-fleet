import sys
from collections.abc import Sequence
from pathlib import Path

import pytest
from conftest import fleet_program
from fake import RecordingRunner

from golem_fleet.cli import application, main
from golem_fleet.cli.program import FleetProgram
from golem_fleet.secrets import secretspec

DATABASE_PASSWORD_ENTRY = "DATABASE_PASSWORD"
REGISTRY_TOKEN_ENTRY = "REGISTRY_TOKEN"
RESOLVED_ENVIRONMENT = {
    DATABASE_PASSWORD_ENTRY: "resolved",
    REGISTRY_TOKEN_ENTRY: "resolved",
}
APPLY_WORDS = ["fleet", "apply"]
PLACEMENT_WORDS = ["placement"]
MACHINE_WORDS = ["machine", "list"]
CONSUMING_ENTRY_MODULE = "strabs_iac.cli"
CONSUMING_PROGRAM_NAME = "strabs-iac"
STATE_BUCKET_COMMAND = "state-bucket"
STATE_BUCKET_TOOL = "aws"
PASSTHROUGH_TOOL = "pulumi"
UNKNOWN_COMMAND = "up"
SUCCESS_EXIT_CODE = 0
REPLACEMENT_EXIT_CODE = 7
POLICY = secretspec.SecretsPolicy(
    required=(DATABASE_PASSWORD_ENTRY, REGISTRY_TOKEN_ENTRY),
    commands_running_without_secrets=frozenset({tuple(PLACEMENT_WORDS)}),
    command_prefixes_running_without_secrets=frozenset({("machine",)}),
)
RUN_AS_THEY_ARE = [
    (fleet_program(), APPLY_WORDS, RESOLVED_ENVIRONMENT),
    (fleet_program(secrets=POLICY), APPLY_WORDS, RESOLVED_ENVIRONMENT),
    (fleet_program(secrets=POLICY), PLACEMENT_WORDS, {}),
    (fleet_program(secrets=POLICY), MACHINE_WORDS, {}),
]


@pytest.mark.parametrize(("program", "words", "environment"), RUN_AS_THEY_ARE)
def test_nothing_is_re_executed_without_a_policy_or_when_the_secrets_are_there(
    program: FleetProgram, words: list[str], environment: dict[str, str]
) -> None:
    assert main.secretspec_reexec_command(program, words, environment) is None


def test_unresolved_secrets_re_execute_the_declared_entry_module() -> None:
    program = fleet_program(secrets=POLICY, entry_module=CONSUMING_ENTRY_MODULE)
    resolved_so_far = {DATABASE_PASSWORD_ENTRY: "resolved"}

    command = main.secretspec_reexec_command(program, APPLY_WORDS, resolved_so_far)

    reason = f"{program.program_name} fleet apply"
    under_secretspec = [secretspec.EXECUTABLE, "run", "--reason", reason]
    consuming_module = [sys.executable, "-m", CONSUMING_ENTRY_MODULE]
    assert command == [*under_secretspec, "--", *consuming_module, *APPLY_WORDS]


def test_a_program_declaring_no_entry_module_cannot_be_re_executed() -> None:
    program = fleet_program(secrets=POLICY)

    with pytest.raises(main.EntryModuleNotDeclared) as raised:
        main.secretspec_reexec_command(program, APPLY_WORDS, {})

    assert raised.value.args == (program.program_name,)


def test_an_extended_app_keeps_its_extra_commands_when_run_through_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    program = fleet_program(program_name=CONSUMING_PROGRAM_NAME)
    runner = RecordingRunner().responds_to([STATE_BUCKET_TOOL])
    app = application.build(program, runner=runner)

    @app.command(name=STATE_BUCKET_COMMAND)
    def create_the_state_bucket() -> None:
        runner.inherit([STATE_BUCKET_TOOL])

    monkeypatch.setattr(sys, "argv", [CONSUMING_PROGRAM_NAME, STATE_BUCKET_COMMAND])

    with pytest.raises(SystemExit) as exited:
        main.run(program, app)

    assert exited.value.code == SUCCESS_EXIT_CODE
    assert runner.last_call.argv == (STATE_BUCKET_TOOL,)


def test_a_scripted_runner_can_be_driven_through_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    program = fleet_program(passthrough=PASSTHROUGH_TOOL)
    runner = RecordingRunner().responds_to_prefix([PASSTHROUGH_TOOL])
    monkeypatch.setattr(sys, "argv", [program.program_name, UNKNOWN_COMMAND])

    with pytest.raises(SystemExit) as exited:
        main.main(program, runner=runner)

    assert exited.value.code == SUCCESS_EXIT_CODE
    assert runner.last_call.argv == (PASSTHROUGH_TOOL, UNKNOWN_COMMAND)


def test_unresolved_secrets_replace_the_process_instead_of_invoking_the_app(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    program = fleet_program(
        secrets=POLICY, entry_module=CONSUMING_ENTRY_MODULE, generated=tmp_path
    )
    runner = RecordingRunner()
    replaced: list[list[str]] = []

    def record(command: Sequence[str]) -> int:
        replaced.append(list(command))
        return REPLACEMENT_EXIT_CODE

    monkeypatch.setattr(main, "replace_this_process_with", record)
    monkeypatch.setattr(sys, "argv", [program.program_name, *APPLY_WORDS])
    for entry in POLICY.required:
        monkeypatch.delenv(entry, raising=False)

    with pytest.raises(SystemExit) as exited:
        main.main(program, runner=runner)

    assert exited.value.code == REPLACEMENT_EXIT_CODE
    assert replaced == [
        secretspec.run_command(
            secretspec.EXECUTABLE,
            program.program_name,
            CONSUMING_ENTRY_MODULE,
            APPLY_WORDS,
        )
    ]
    assert runner.calls == ()

import json
from pathlib import Path

import pytest
from conftest import (
    MALFORMED_FLEET_KEY,
    OVH_IPV4,
    OVH_IPV6,
    OVH_MACHINE,
    OVH_SERVICE,
    STATIC_IPV4,
    STATIC_MACHINE,
    WELL_FORMED_FLEET_KEY,
    ScriptedOvhTransport,
    declare_ovh_credentials,
    every_address,
    fleet_program,
    only_the_ovh_address,
    ovh_machine,
    ovh_transport_answering,
    program_without_bare_metal,
    static_machine,
)
from fake import RecordingRunner
from typer.testing import CliRunner, Result

from golem_fleet.addresses import source
from golem_fleet.cli import machine_commands
from golem_fleet.cli.program import FleetProgram
from golem_fleet.execution import ports
from golem_fleet.fleet import machines, placements
from golem_fleet.outputs import cloud_config
from golem_fleet.secrets import keys

SSH = "ssh"
OVHCLOUD = "ovhcloud"
PUBLIC_KEY_TEXT = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5 console\n"
AGENT_BINARY_CONTENT = b"golemd"
SSH_FAILED_EXIT_CODE = 3
INSTALL_STEP = "installing the operating system"
GOLEM_AUTH_TOKEN = "golem-auth-token-for-the-fleet"
UNPLACED = "no-such-machine"
AGENT_VARIABLE = fleet_program().agent_binary_variable
OVHCLOUD_WORDS = {
    "info": ("baremetal", "get"),
    "tasks": ("baremetal", "list-tasks"),
    "interventions": ("baremetal", "list-interventions"),
    "kvm": ("baremetal", "ipmi", "get-access"),
    "rescue": ("baremetal", "reboot-rescue"),
}
LISTING_COMMANDS = [
    (["list"], f"{OVH_MACHINE}\t{OVH_SERVICE}\n{STATIC_MACHINE}"),
    (["address", OVH_MACHINE], OVH_IPV4),
    (["address6", OVH_MACHINE], OVH_IPV6),
]
NAMED_FAILURES = [
    (
        ["address6", STATIC_MACHINE],
        machine_commands.MachineAnswersOnIpv4Only,
        STATIC_MACHINE,
    ),
    (["address", UNPLACED], placements.MachineIsNotInTheFleet, UNPLACED),
    (
        ["info", STATIC_MACHINE],
        machine_commands.MachineIsNotOvhBareMetal,
        STATIC_MACHINE,
    ),
    (["agent-status"], machine_commands.NoMachineToActOn, OVH_MACHINE),
    (["cloud-config", UNPLACED], placements.MachineIsNotInTheFleet, UNPLACED),
    (
        ["agent", OVH_MACHINE],
        machine_commands.AgentBinaryVariableNotSet,
        AGENT_VARIABLE,
    ),
]
REMOTE_SCRIPTS = [
    ("agent-status", "systemctl is-active golemd"),
    ("kexec", "kexec --load"),
]
OVH_ONLY_VERBS = frozenset(
    {"info", "tasks", "interventions", "kvm", "rescue", "status", "console"}
)
PROVIDER_AGNOSTIC_VERBS = frozenset(
    {"list", "address", "address6", "cloud-config", "agent", "kexec", "diagnose"}
)
UNDECLARED_CREDENTIALS = [
    (machine_commands.GOLEM_AUTH_TOKEN_VARIABLE, WELL_FORMED_FLEET_KEY),
    (keys.ENVIRONMENT_VARIABLE, GOLEM_AUTH_TOKEN),
]


def ssh_runner() -> RecordingRunner:
    runner = RecordingRunner()
    runner.responds_to_prefix([SSH])
    runner.responds_to_prefix([OVHCLOUD])
    return runner


def ssh_runner_failing_on(address: str) -> RecordingRunner:
    runner = ssh_runner()
    prefix = [SSH, ssh_destination(address)]
    return runner.responds_to_prefix(prefix, exit_code=SSH_FAILED_EXIT_CODE)


def ssh_destination(address: str) -> str:
    return f"root@{address}"


def machine_command(
    words: list[str], program: FleetProgram, runner: ports.Runner
) -> Result:
    return CliRunner().invoke(machine_commands.build(program, runner), words)


def console_command(key_path: Path, runner: ports.Runner) -> Result:
    words = ["console", OVH_MACHINE, "--ssh-key", str(key_path)]
    return machine_command(words, fleet_program(), runner)


def cloud_config_of(machine_name: str) -> Result:
    return machine_command(
        ["cloud-config", machine_name], fleet_program(), ssh_runner()
    )


def installed_transport() -> ScriptedOvhTransport:
    status = json.dumps({"progress": [{"comment": INSTALL_STEP, "status": "done"}]})
    return ovh_transport_answering(
        {f"/dedicated/server/{OVH_SERVICE}/install/status": status}
    )


def status_command(transport: ScriptedOvhTransport, slept: list[float]) -> Result:
    app = machine_commands.build(
        fleet_program(), ssh_runner(), transport=transport, sleep=slept.append
    )
    return CliRunner().invoke(app, ["status", OVH_MACHINE])


def declare_golem_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(machine_commands.GOLEM_AUTH_TOKEN_VARIABLE, GOLEM_AUTH_TOKEN)
    monkeypatch.setenv(keys.ENVIRONMENT_VARIABLE, WELL_FORMED_FLEET_KEY)


FANOUT_FAILURES = [
    (every_address(), ssh_runner_failing_on(STATIC_IPV4)),
    (only_the_ovh_address(), ssh_runner()),
]


@pytest.mark.parametrize(("words", "expected_stdout"), LISTING_COMMANDS)
def test_a_listing_command_prints_what_the_fleet_and_the_addresses_declare(
    words: list[str], expected_stdout: str
) -> None:
    result = machine_command(words, fleet_program(), ssh_runner())

    assert result.exit_code == 0
    assert result.stdout.strip() == expected_stdout


@pytest.mark.parametrize(("words", "expected_fault", "expected_value"), NAMED_FAILURES)
def test_a_named_failure_is_reported_before_anything_is_run(
    monkeypatch: pytest.MonkeyPatch,
    words: list[str],
    expected_fault: type[Exception],
    expected_value: str,
) -> None:
    monkeypatch.delenv(AGENT_VARIABLE, raising=False)
    runner = ssh_runner()

    result = machine_command(words, fleet_program(), runner)

    assert result.exit_code == 1
    assert expected_fault.__name__ in result.stderr
    assert expected_value in result.stderr
    assert runner.calls == ()


@pytest.mark.parametrize(("command", "ovhcloud_words"), OVHCLOUD_WORDS.items())
def test_every_ovh_command_runs_the_ovhcloud_argv_for_the_service(
    command: str, ovhcloud_words: tuple[str, ...]
) -> None:
    runner = ssh_runner()
    expected = (OVHCLOUD, *ovhcloud_words, OVH_SERVICE)

    result = machine_command([command, OVH_MACHINE], fleet_program(), runner)

    assert result.exit_code == 0
    assert runner.last_call.argv[: len(expected)] == expected


def test_console_sends_the_public_key_or_names_the_path_it_could_not_read(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "absent.pub"
    key_path = tmp_path / "id_ed25519.pub"
    key_path.write_text(PUBLIC_KEY_TEXT, encoding="utf-8")
    runner = ssh_runner()

    refused = console_command(missing, runner)
    sent = console_command(key_path, runner)

    assert refused.exit_code == 1
    assert machine_commands.SshPublicKeyNotFound.__name__ in refused.stderr
    assert str(missing) in refused.stderr
    assert sent.exit_code == 0
    assert runner.last_call.argv[0] == OVHCLOUD
    assert PUBLIC_KEY_TEXT.rstrip() in runner.last_call.argv


@pytest.mark.parametrize(("command", "script_fragment"), REMOTE_SCRIPTS)
def test_an_operation_on_one_machine_runs_its_script_at_the_resolved_address(
    command: str, script_fragment: str
) -> None:
    runner = ssh_runner()

    result = machine_command([command, OVH_MACHINE], fleet_program(), runner)

    assert result.exit_code == 0
    over_ssh = runner.calls_to([SSH])[0]
    assert over_ssh.argv[:2] == (SSH, ssh_destination(OVH_IPV4))
    assert script_fragment in over_ssh.argv[2]


def test_diagnose_writes_a_report_named_after_the_machine(tmp_path: Path) -> None:
    program = fleet_program(generated=tmp_path)

    result = machine_command(["diagnose", OVH_MACHINE], program, ssh_runner())

    report = tmp_path / "diagnostics" / f"{OVH_MACHINE}.txt"
    assert result.exit_code == 0
    assert report.is_file()
    assert result.stdout.strip() == str(report)


def test_agent_reads_the_binary_path_from_the_declared_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = tmp_path / "golemd"
    binary.write_bytes(AGENT_BINARY_CONTENT)
    monkeypatch.setenv(AGENT_VARIABLE, str(binary))
    runner = ssh_runner()

    result = machine_command(["agent", OVH_MACHINE], fleet_program(), runner)

    assert result.exit_code == 0
    assert runner.last_call.stdin == AGENT_BINARY_CONTENT


def test_agent_status_across_every_machine_reports_one_line_each() -> None:
    runner = ssh_runner()

    result = machine_command(["agent-status", "--all"], fleet_program(), runner)

    assert result.exit_code == 0
    assert f"{OVH_MACHINE}\tok" in result.output
    assert f"{STATIC_MACHINE}\tok" in result.output
    assert len(runner.calls_to([SSH])) == 2


@pytest.mark.parametrize(("addresses", "runner"), FANOUT_FAILURES)
def test_one_failing_machine_fails_its_line_the_fan_out_and_prints_its_output(
    addresses: tuple[source.Source, ...], runner: RecordingRunner
) -> None:
    program = fleet_program(addresses=addresses)

    result = machine_command(["agent-status", "--all"], program, runner)

    assert result.exit_code == 1
    assert f"{OVH_MACHINE}\tok" in result.stdout
    assert f"{STATIC_MACHINE}\tfailed" in result.stdout
    assert result.stderr.startswith(machine_commands.FAILURE_OUTPUT_INDENT)
    assert STATIC_MACHINE in result.stderr


def test_the_reinstall_policy_is_the_one_the_machine_declares() -> None:
    requested = machines.ReinstallRequested(7)
    policy_of = machine_commands.reinstall_policy_of

    assert policy_of(static_machine()) == machines.ProtectedFromReinstall()
    assert policy_of(ovh_machine(reinstall=requested)) == requested


def test_cloud_config_seeds_each_machine_with_the_credentials_it_can_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    declare_golem_credentials(monkeypatch)

    bare_metal = cloud_config_of(OVH_MACHINE)
    without_ovh = cloud_config_of(STATIC_MACHINE)

    assert bare_metal.exit_code == 0
    assert bare_metal.stdout.splitlines()[0] == cloud_config.HEADER
    assert cloud_config.base64_of(GOLEM_AUTH_TOKEN) in bare_metal.stdout
    assert cloud_config.base64_of(WELL_FORMED_FLEET_KEY) in bare_metal.stdout
    assert bare_metal.stderr == ""
    assert without_ovh.exit_code == 0
    assert cloud_config.REINSTALL_GENERATION_PREFIX not in without_ovh.stdout


@pytest.mark.parametrize(("undeclared", "other_secret"), UNDECLARED_CREDENTIALS)
def test_an_undeclared_golem_credential_names_it_and_echoes_no_other_secret(
    monkeypatch: pytest.MonkeyPatch,
    undeclared: str,
    other_secret: str,
) -> None:
    declare_golem_credentials(monkeypatch)
    monkeypatch.delenv(undeclared)

    result = cloud_config_of(OVH_MACHINE)

    assert result.exit_code == 1
    assert machine_commands.GolemCredentialVariableNotSet.__name__ in result.stderr
    assert undeclared in result.stderr
    assert other_secret not in result.output
    assert cloud_config.base64_of(other_secret) not in result.output


def test_a_malformed_fleet_key_is_refused_without_echoing_either_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    declare_golem_credentials(monkeypatch)
    monkeypatch.setenv(keys.ENVIRONMENT_VARIABLE, MALFORMED_FLEET_KEY)

    result = cloud_config_of(OVH_MACHINE)

    assert result.exit_code == 1
    assert keys.WrongLength.__name__ in result.stderr
    assert MALFORMED_FLEET_KEY not in result.output
    assert GOLEM_AUTH_TOKEN not in result.output


def test_status_follows_the_install_and_exits_zero_when_none_is_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    declare_ovh_credentials(monkeypatch)
    slept: list[float] = []

    running = status_command(installed_transport(), slept)
    absent = status_command(ovh_transport_answering({}), slept)

    assert running.exit_code == 0
    assert INSTALL_STEP in running.stdout
    assert absent.exit_code == 0
    assert OVH_MACHINE in absent.stdout
    assert slept == []


def machine_verbs_of(program: FleetProgram) -> frozenset[str]:
    app = machine_commands.build(program, RecordingRunner())
    return frozenset(
        info.name for info in app.registered_commands if info.name is not None
    )


def test_the_ovh_only_verbs_appear_only_for_a_fleet_carrying_bare_metal() -> None:
    carrying = machine_verbs_of(fleet_program())
    without = machine_verbs_of(program_without_bare_metal())

    assert carrying >= OVH_ONLY_VERBS
    assert carrying >= PROVIDER_AGNOSTIC_VERBS
    assert OVH_ONLY_VERBS.isdisjoint(without)
    assert without >= PROVIDER_AGNOSTIC_VERBS

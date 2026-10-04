import sys

from golem_fleet.secrets import secretspec

PROGRAM = "golem-fleet"
MODULE = "golem_fleet.cli.main"
POLICY = secretspec.SecretsPolicy(
    required=("GOLEM_SECRET_KEY", "REGISTRY_PULL_AUTH"),
    commands_running_without_secrets=frozenset({("version",), ("fleet", "show")}),
    command_prefixes_running_without_secrets=frozenset({("docs",)}),
)


def test_the_re_exec_and_the_check_commands_explain_themselves() -> None:
    assert secretspec.run_command(
        "/usr/bin/secretspec", PROGRAM, MODULE, ["deploy", "dull-01"]
    ) == [
        "/usr/bin/secretspec",
        "run",
        "--reason",
        "golem-fleet deploy dull-01",
        "--",
        sys.executable,
        "-m",
        MODULE,
        "deploy",
        "dull-01",
    ]
    assert secretspec.check_command(PROGRAM) == [
        "secretspec",
        "check",
        "--explain",
        "--reason",
        PROGRAM,
    ]


def test_secrets_are_resolved_only_when_every_required_variable_is_filled() -> None:
    assert POLICY.are_resolved({"GOLEM_SECRET_KEY": "ab", "REGISTRY_PULL_AUTH": "cd"})
    assert not POLICY.are_resolved({"GOLEM_SECRET_KEY": "ab"})
    assert not POLICY.are_resolved({"GOLEM_SECRET_KEY": "ab", "REGISTRY_PULL_AUTH": ""})


def test_only_the_exempted_commands_run_without_secrets() -> None:
    assert not POLICY.needs_secrets([])
    assert not POLICY.needs_secrets(["deploy", "--help"])
    assert not POLICY.needs_secrets(["deploy", "-h"])
    assert not POLICY.needs_secrets(["version"])
    assert not POLICY.needs_secrets(["fleet", "show"])
    assert not POLICY.needs_secrets(["docs", "render", "--out", "site"])
    assert POLICY.needs_secrets(["fleet", "render"])
    assert POLICY.needs_secrets(["deploy", "dull-01"])


def test_a_policy_without_exemptions_always_needs_secrets() -> None:
    assert secretspec.SecretsPolicy(required=("GOLEM_SECRET_KEY",)).needs_secrets(
        ["version"]
    )

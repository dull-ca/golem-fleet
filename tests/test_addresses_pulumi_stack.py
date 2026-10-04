import pytest
from fake import RecordingRunner

from golem_fleet.addresses import pulumi_stack, source

ADDRESSES_OUTPUT = "machineAddresses"
DETAILED_STDOUT = (
    '{"machineAddresses": {"dull-01": {"ipv4": "203.0.113.7", '
    '"ipv6": "2001:db8::7"}}, "pullCredentials": "{}"}'
)
DEFAULT_STACK = "prod"
PULUMI_PREFIX = ("pulumi", "stack", "output")
PULUMI_ARGV = (*PULUMI_PREFIX, "--json", "--show-secrets", "--stack")


def exporting(
    stdout: str = "", *, stderr: str = "", exit_code: int = 0
) -> RecordingRunner:
    return RecordingRunner().responds_to_prefix(
        PULUMI_PREFIX, stdout=stdout, stderr=stderr, exit_code=exit_code
    )


@pytest.mark.parametrize("stack", [DEFAULT_STACK, "staging"])
def test_resolve_shows_secrets_in_the_declared_stack(stack: str) -> None:
    runner = exporting(DETAILED_STDOUT)

    assert pulumi_stack.Output(ADDRESSES_OUTPUT, stack=stack).resolve(runner) == {
        "dull-01": source.MachineAddresses("203.0.113.7", "2001:db8::7")
    }
    assert runner.last_call.argv == (*PULUMI_ARGV, stack)


def test_a_failing_pulumi_carries_its_stack_exit_code_and_stderr() -> None:
    runner = exporting(exit_code=255, stderr="  no stack named prod\n")

    with pytest.raises(source.Unavailable) as raised:
        pulumi_stack.Output(ADDRESSES_OUTPUT).resolve(runner)

    assert raised.value.args == (DEFAULT_STACK, 255, "no stack named prod")


def test_a_missing_output_carries_the_output_the_stack_and_what_it_exports() -> None:
    with pytest.raises(pulumi_stack.NoSuchOutput) as raised:
        pulumi_stack.Output("fleetAddresses").resolve(exporting(DETAILED_STDOUT))

    assert raised.value.args == (
        "fleetAddresses",
        DEFAULT_STACK,
        "machineAddresses",
        "pullCredentials",
    )

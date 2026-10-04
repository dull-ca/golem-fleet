from pathlib import Path

import pytest
from fake import (
    CAPTURE_METHOD,
    INHERIT_METHOD,
    INTO_FILE_METHOD,
    RecordingRunner,
    UnconfiguredCommand,
)

STACK_OUTPUT_ARGV = ("pulumi", "stack", "output")
SSH_ARGV = ("ssh", "golem-one", "uptime")
VERSION_ARGV = ("pulumi", "version")
BINARY_PAYLOAD = b"\x00\xff\xfe golemd \x00\x7fELF\x00"
PULUMI_ENVIRONMENT = {"PULUMI_SKIP_UPDATE_CHECK": "1"}


def test_calls_are_recorded_in_order_with_everything_they_were_given(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "output.json"
    runner = RecordingRunner().responds_to_prefix(())

    runner.capture(STACK_OUTPUT_ARGV, environment=PULUMI_ENVIRONMENT)
    runner.inherit(SSH_ARGV, cwd=tmp_path, stdin=BINARY_PAYLOAD)
    runner.into_file(VERSION_ARGV, destination)

    assert tuple((call.method, call.argv) for call in runner.calls) == (
        (CAPTURE_METHOD, STACK_OUTPUT_ARGV),
        (INHERIT_METHOD, SSH_ARGV),
        (INTO_FILE_METHOD, VERSION_ARGV),
    )
    assert runner.calls[0].environment == PULUMI_ENVIRONMENT
    assert runner.calls[1].cwd == tmp_path
    assert runner.calls[1].stdin == BINARY_PAYLOAD
    assert runner.last_call.destination == destination


def test_an_exact_response_wins_over_a_prefix_that_also_matches() -> None:
    runner = RecordingRunner().responds_to_prefix(("ssh",), exit_code=7)
    runner.responds_to(SSH_ARGV, raises=UnconfiguredCommand(SSH_ARGV))

    assert runner.inherit(("ssh", "golem-two", "uptime")) == 7

    with pytest.raises(UnconfiguredCommand):
        runner.inherit(SSH_ARGV)

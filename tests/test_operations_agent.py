from pathlib import Path

import pytest
from fake import RecordingRunner

from golem_fleet.operations import agent

ADDRESS = "203.0.113.7"
SSH_PREFIX = ("ssh",)
BINARY_CONTENT = b"\x7fELF\x02\x01\x01golemd\x00\xff"
EXPECTED_INSTALL_SCRIPT = (
    "install -m 0755 /dev/null /usr/local/bin/golemd.staged"
    " && cat >/usr/local/bin/golemd.staged"
    " && mv /usr/local/bin/golemd.staged /usr/local/bin/golemd"
    " && systemctl restart golemd"
    " && systemctl is-active golemd"
    " && /usr/local/bin/golemd --version"
)
EXPECTED_STATUS_SCRIPT = (
    "systemctl is-active golemd; systemctl status golemd --no-pager --lines=5 || true"
)


def test_install_refuses_a_missing_binary_then_streams_its_bytes(
    tmp_path: Path,
) -> None:
    runner = RecordingRunner().responds_to_prefix(SSH_PREFIX)
    binary = tmp_path / "golemd"

    with pytest.raises(agent.BinaryNotFound) as raised:
        agent.install(runner, ADDRESS, binary)

    assert raised.value.args == (binary,)
    assert runner.calls == ()

    binary.write_bytes(BINARY_CONTENT)

    assert agent.install(runner, ADDRESS, binary) == 0
    assert runner.last_call.argv == (
        "ssh",
        f"root@{ADDRESS}",
        EXPECTED_INSTALL_SCRIPT,
    )
    assert runner.last_call.stdin == BINARY_CONTENT


def test_status_runs_the_status_script_over_ssh() -> None:
    runner = RecordingRunner().responds_to_prefix(SSH_PREFIX)

    exit_code = agent.status(runner, ADDRESS)

    assert exit_code == 0
    assert runner.last_call.argv == (
        "ssh",
        f"root@{ADDRESS}",
        EXPECTED_STATUS_SCRIPT,
    )
    assert runner.last_call.stdin is None

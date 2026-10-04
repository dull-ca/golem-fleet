import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest
from fake import INTO_FILE_METHOD, RecordedCall, RecordingRunner

from golem_fleet.operations import diagnostics

ADDRESS = "203.0.113.7"
MACHINE_NAME = "worker-01"
OPEN_UMASK = 0o000


@pytest.fixture
def open_umask() -> Iterator[None]:
    previous = os.umask(OPEN_UMASK)
    try:
        yield
    finally:
        os.umask(previous)


def test_collect_captures_the_script_into_a_report_named_for_the_machine(
    tmp_path: Path,
) -> None:
    runner = RecordingRunner().responds_to_prefix(("ssh",))

    report = diagnostics.collect(
        runner, MACHINE_NAME, ADDRESS, tmp_path / "diagnostics"
    )

    assert report == tmp_path / "diagnostics" / "worker-01.txt"
    assert "\\\n" not in diagnostics.SCRIPT
    assert runner.calls == (
        RecordedCall(
            method=INTO_FILE_METHOD,
            argv=("ssh", f"root@{ADDRESS}", "bash -s"),
            stdin=diagnostics.SCRIPT,
            destination=report,
        ),
    )


@pytest.mark.usefixtures("open_umask")
def test_collect_creates_the_missing_parents_then_accepts_them_next_time(
    tmp_path: Path,
) -> None:
    runner = RecordingRunner().responds_to_prefix(("ssh",))
    into = tmp_path / "runs" / "today"

    diagnostics.collect(runner, MACHINE_NAME, ADDRESS, into)

    assert into.is_dir()
    assert stat.S_IMODE(into.stat().st_mode) == 0o755
    assert diagnostics.collect(runner, MACHINE_NAME, ADDRESS, into).parent == into

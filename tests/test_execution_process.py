import os
import sys
from pathlib import Path

import pytest

from golem_fleet.execution import ports, process

STDOUT_FRAGMENT = "on stdout"
STDERR_FRAGMENT = "on stderr"
FAILING_EXIT_CODE = 3
WRITE_BOTH_STREAMS_AND_FAIL = (
    "import sys; "
    f"sys.stdout.write({STDOUT_FRAGMENT!r}); "
    f"sys.stderr.write({STDERR_FRAGMENT!r}); "
    f"sys.exit({FAILING_EXIT_CODE})"
)
MARKER_NAME = "GOLEM_FLEET_MARKER"
MARKER_VALUE = "fleet"
NAME_NOT_ON_PATH = "golem-fleet-executable-that-does-not-exist"
BINARY_PAYLOAD = b"\x00\xff\xfe golemd \x00\x7fELF\x00"
INVALID_UTF8 = bytes([255, 254])
REPLACEMENT_CHARACTER = "�"
NON_ASCII_OUTPUT = "gölemd is up ✓"
FIELD_SEPARATOR = "\n"
REPORT_THE_ENVIRONMENT_THE_DIRECTORY_AND_STDIN = (
    "import os,sys; "
    f"sys.stdout.buffer.write({(NON_ASCII_OUTPUT + FIELD_SEPARATOR).encode()!r}); "
    f"sys.stdout.buffer.write({FIELD_SEPARATOR!r}.join(("
    f"os.environ[{MARKER_NAME!r}], str('PATH' in os.environ), os.getcwd(), "
    "sys.stdin.buffer.read().hex())).encode()); "
    f"sys.stderr.buffer.write(bytes({list(INVALID_UTF8)}))"
)
EVERY_STDIN_ROUND_TRIP = [(MARKER_VALUE, MARKER_VALUE.encode()), (BINARY_PAYLOAD,) * 2]


def python(source: str) -> tuple[str, ...]:
    return (sys.executable, "-c", source)


def test_capture_returns_both_streams_and_leaves_the_failure_to_the_caller() -> None:
    failing = process.Runner().capture(python(WRITE_BOTH_STREAMS_AND_FAIL))

    assert (failing.stdout, failing.stderr) == (STDOUT_FRAGMENT, STDERR_FRAGMENT)
    assert failing.argv == python(WRITE_BOTH_STREAMS_AND_FAIL)
    assert not failing.ok

    with pytest.raises(ports.CommandFailed) as failure:
        failing.raise_for_exit_code()

    assert failure.value.args == (failing.argv, FAILING_EXIT_CODE, STDERR_FRAGMENT)

    succeeding = process.Runner().capture(python("pass"))

    assert succeeding.raise_for_exit_code() is succeeding


@pytest.mark.parametrize(("stdin", "sent"), EVERY_STDIN_ROUND_TRIP)
def test_each_stdin_path_merges_the_environment_keeps_the_cwd_and_decodes_as_utf8(
    stdin: str | bytes,
    sent: bytes,
    tmp_path: Path,
) -> None:
    completed = process.Runner().capture(
        python(REPORT_THE_ENVIRONMENT_THE_DIRECTORY_AND_STDIN),
        cwd=tmp_path,
        environment={MARKER_NAME: MARKER_VALUE},
        stdin=stdin,
    )
    greeting, marker, kept_path, directory, hexed = completed.stdout.split(
        FIELD_SEPARATOR
    )

    assert (greeting, marker, kept_path) == (NON_ASCII_OUTPUT, MARKER_VALUE, "True")
    assert Path(directory).resolve() == tmp_path.resolve()
    assert bytes.fromhex(hexed) == sent
    assert completed.stderr == REPLACEMENT_CHARACTER * len(INVALID_UTF8)
    assert MARKER_NAME not in os.environ


def test_inherit_returns_the_exit_code() -> None:
    assert process.Runner().inherit(python(WRITE_BOTH_STREAMS_AND_FAIL)) == (
        FAILING_EXIT_CODE
    )


def test_into_file_truncates_the_destination_and_captures_both_streams(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "combined.log"
    destination.write_text("stale", encoding="utf-8")

    exit_code = process.Runner().into_file(
        python(WRITE_BOTH_STREAMS_AND_FAIL), destination, stdin=BINARY_PAYLOAD
    )
    written = destination.read_bytes()

    assert exit_code == FAILING_EXIT_CODE
    assert STDOUT_FRAGMENT.encode() in written
    assert STDERR_FRAGMENT.encode() in written
    assert b"stale" not in written


def test_every_method_refuses_an_executable_that_is_not_on_path(
    tmp_path: Path,
) -> None:
    runner = process.Runner()
    never_written = tmp_path / "never-written.log"

    with pytest.raises(ports.ExecutableNotFound) as failure:
        runner.capture((NAME_NOT_ON_PATH,))

    assert failure.value.args == (NAME_NOT_ON_PATH,)

    with pytest.raises(ports.ExecutableNotFound):
        runner.inherit((NAME_NOT_ON_PATH,))

    with pytest.raises(ports.ExecutableNotFound):
        runner.into_file((NAME_NOT_ON_PATH,), never_written)

    assert not never_written.exists()

from pathlib import Path

from fake import RecordingRunner

from golem_fleet.operations import ssh

ADDRESS = "203.0.113.7"
SCRIPT = "uptime"
SSH_ARGV = ("ssh", f"root@{ADDRESS}", SCRIPT)
FAILING_EXIT_CODE = 3


def test_run_forwards_stdin_and_cwd_and_returns_the_exit_code() -> None:
    runner = RecordingRunner().responds_to(SSH_ARGV, exit_code=FAILING_EXIT_CODE)

    exit_code = ssh.run(runner, ADDRESS, SCRIPT, stdin="payload", cwd=Path("/srv"))

    assert exit_code == FAILING_EXIT_CODE
    assert runner.last_call.argv == SSH_ARGV
    assert runner.last_call.stdin == "payload"
    assert runner.last_call.cwd == Path("/srv")


def test_run_into_file_passes_the_destination_through(tmp_path: Path) -> None:
    runner = RecordingRunner().responds_to(SSH_ARGV)
    report = tmp_path / "report.txt"

    exit_code = ssh.run_into_file(runner, ADDRESS, SCRIPT, report, stdin="script")

    assert exit_code == 0
    assert runner.last_call.argv == SSH_ARGV
    assert runner.last_call.destination == report
    assert runner.last_call.stdin == "script"

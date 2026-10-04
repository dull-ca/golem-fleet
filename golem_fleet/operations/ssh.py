from pathlib import Path

from golem_fleet.execution import ports

ACCOUNT = "root"


def destination(address: str) -> str:
    return f"{ACCOUNT}@{address}"


def command(address: str, script: str) -> list[str]:
    return ["ssh", destination(address), script]


def run(
    runner: ports.Runner,
    address: str,
    script: str,
    *,
    stdin: str | bytes | None = None,
    cwd: Path | None = None,
) -> int:
    return runner.inherit(command(address, script), cwd=cwd, stdin=stdin)


def run_into_file(
    runner: ports.Runner,
    address: str,
    script: str,
    report: Path,
    *,
    stdin: str | bytes | None = None,
    cwd: Path | None = None,
) -> int:
    return runner.into_file(command(address, script), report, cwd=cwd, stdin=stdin)

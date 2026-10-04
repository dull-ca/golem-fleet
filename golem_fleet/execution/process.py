import os
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import IO

from golem_fleet.execution import ports

DESTINATION_FILE_MODE = 0o644
DESTINATION_OPEN_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
CHILD_OUTPUT_ENCODING = "utf-8"
CHILD_OUTPUT_DECODING_ERRORS = "replace"


def resolved_command(argv: Sequence[str]) -> list[str]:
    executable = shutil.which(argv[0])
    if executable is None:
        raise ports.ExecutableNotFound(argv[0])
    return [executable, *argv[1:]]


def decoded(output: str | bytes | None) -> str:
    if isinstance(output, bytes):
        return output.decode(CHILD_OUTPUT_ENCODING, CHILD_OUTPUT_DECODING_ERRORS)
    return output or ""


def run_child(
    argv: Sequence[str],
    *,
    cwd: Path | None,
    environment: Mapping[str, str] | None,
    stdin: str | bytes | None,
    stdout: IO[bytes] | int | None = None,
    stderr: int | None = None,
) -> ports.Completed:
    command = resolved_command(argv)
    child_environment = None if environment is None else {**os.environ, **environment}
    if isinstance(stdin, bytes):
        finished = subprocess.run(
            command,
            check=False,
            input=stdin,
            stdout=stdout,
            stderr=stderr,
            cwd=cwd,
            env=child_environment,
        )
    else:
        finished = subprocess.run(
            command,
            check=False,
            encoding=CHILD_OUTPUT_ENCODING,
            errors=CHILD_OUTPUT_DECODING_ERRORS,
            input=stdin,
            stdout=stdout,
            stderr=stderr,
            cwd=cwd,
            env=child_environment,
        )
    return ports.Completed(
        argv=tuple(argv),
        exit_code=finished.returncode,
        stdout=decoded(finished.stdout),
        stderr=decoded(finished.stderr),
    )


class Runner:
    def capture(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        environment: Mapping[str, str] | None = None,
        stdin: str | bytes | None = None,
    ) -> ports.Completed:
        return run_child(
            argv,
            cwd=cwd,
            environment=environment,
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def inherit(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        environment: Mapping[str, str] | None = None,
        stdin: str | bytes | None = None,
    ) -> int:
        return run_child(argv, cwd=cwd, environment=environment, stdin=stdin).exit_code

    def into_file(
        self,
        argv: Sequence[str],
        destination: Path,
        *,
        cwd: Path | None = None,
        environment: Mapping[str, str] | None = None,
        stdin: str | bytes | None = None,
    ) -> int:
        command = resolved_command(argv)
        descriptor = os.open(destination, DESTINATION_OPEN_FLAGS, DESTINATION_FILE_MODE)
        with os.fdopen(descriptor, "wb") as sink:
            return run_child(
                command,
                cwd=cwd,
                environment=environment,
                stdin=stdin,
                stdout=sink,
                stderr=subprocess.STDOUT,
            ).exit_code

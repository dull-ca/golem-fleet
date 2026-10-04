import os
import re
import shutil
import signal
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import FrameType

from golem_fleet.fault import Fault

LENGTH = 128
LOWERCASE_HEXADECIMAL = re.compile(r"\A[0-9a-f]*\Z")
ENVIRONMENT_VARIABLE = "GOLEM_SECRET_KEY"
FILE_ENVIRONMENT_VARIABLE = "GOLEM_SECRET_KEY_FILE"
FILENAME = "secret-key"
FILE_MODE = 0o600
DIRECTORY_MODE = 0o700
RUNTIME_DIRECTORY_VARIABLE = "XDG_RUNTIME_DIR"
SHARED_MEMORY_ROOT = Path("/dev") / "shm"
INTERRUPTED_EXIT_CODE = 130
TERMINATED_EXIT_CODE = 143
REMOVAL_SIGNAL_EXIT_CODES = {
    signal.SIGINT: INTERRUPTED_EXIT_CODE,
    signal.SIGTERM: TERMINATED_EXIT_CODE,
}


class WrongLength(Fault):
    pass


class NotLowercaseHexadecimal(Fault):
    pass


@dataclass(frozen=True)
class FleetKey:
    value: str

    def __post_init__(self) -> None:
        if len(self.value) != LENGTH:
            raise WrongLength(len(self.value), LENGTH)
        if LOWERCASE_HEXADECIMAL.match(self.value) is None:
            raise NotLowercaseHexadecimal


def secret_key_root() -> Path:
    runtime_directory = os.environ.get(RUNTIME_DIRECTORY_VARIABLE, "")
    return Path(runtime_directory) if runtime_directory else SHARED_MEMORY_ROOT


def install_key_removal_handlers(directory: Path) -> Callable[[], None]:
    previous = {
        number: signal.getsignal(number) for number in REMOVAL_SIGNAL_EXIT_CODES
    }

    def remove_directory_and_exit(number: int, frame: FrameType | None) -> None:
        del frame
        shutil.rmtree(directory, ignore_errors=True)
        sys.exit(REMOVAL_SIGNAL_EXIT_CODES[signal.Signals(number)])

    for number in previous:
        signal.signal(number, remove_directory_and_exit)

    def restore_previous_handlers() -> None:
        for number, handler in previous.items():
            signal.signal(number, handler)

    return restore_previous_handlers


@contextmanager
def materialised(key: FleetKey) -> Iterator[Path]:
    directory = Path(tempfile.mkdtemp(prefix="golem-fleet-key-", dir=secret_key_root()))
    restore_previous_handlers = install_key_removal_handlers(directory)
    try:
        directory.chmod(DIRECTORY_MODE)
        key_path = directory / FILENAME
        key_path.touch(mode=FILE_MODE)
        key_path.chmod(FILE_MODE)
        key_path.write_text(key.value, encoding="utf-8")
        yield key_path
    finally:
        restore_previous_handlers()
        shutil.rmtree(directory, ignore_errors=True)

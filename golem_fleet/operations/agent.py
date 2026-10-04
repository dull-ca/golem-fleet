from pathlib import Path

from golem_fleet.execution import ports
from golem_fleet.fault import Fault
from golem_fleet.operations import ssh

SERVICE = "golemd"
INSTALLED_PATH = "/usr/local/bin/golemd"
STAGED_PATH = "/usr/local/bin/golemd.staged"
FILE_MODE = "0755"
STATUS_JOURNAL_LINES = 5
INSTALL_SCRIPT = " && ".join(
    (
        f"install -m {FILE_MODE} /dev/null {STAGED_PATH}",
        f"cat >{STAGED_PATH}",
        f"mv {STAGED_PATH} {INSTALLED_PATH}",
        f"systemctl restart {SERVICE}",
        f"systemctl is-active {SERVICE}",
        f"{INSTALLED_PATH} --version",
    )
)
STATUS_SCRIPT = (
    f"systemctl is-active {SERVICE}; "
    f"systemctl status {SERVICE} --no-pager --lines={STATUS_JOURNAL_LINES} "
    f"|| true"
)


class BinaryNotFound(Fault):
    pass


def install(runner: ports.Runner, address: str, binary: Path) -> int:
    if not binary.is_file():
        raise BinaryNotFound(binary)
    return ssh.run(runner, address, INSTALL_SCRIPT, stdin=binary.read_bytes())


def status(runner: ports.Runner, address: str) -> int:
    return ssh.run(runner, address, STATUS_SCRIPT)

from pathlib import Path

from golem_fleet.execution import ports
from golem_fleet.operations import ssh

DIRECTORY_MODE = 0o755
READ_SCRIPT_FROM_STDIN = "bash -s"
SCRIPT = """#!/usr/bin/env bash
set -u

echo "=== kernel ==="
uname -srmo

echo "=== uptime ==="
uptime

echo "=== golemd ==="
systemctl is-active golemd || true

echo "=== failed units ==="
systemctl --failed --no-pager --no-legend || true

echo "=== container units ==="
systemctl list-units --no-pager --no-legend --all 'podman*' 'container*' || true

echo "=== listening sockets ==="
ss -tulpn || true

echo "=== golemd journal ==="
journalctl -u golemd --no-pager --lines=50 || true
"""


def collect(runner: ports.Runner, machine_name: str, address: str, into: Path) -> Path:
    into.mkdir(mode=DIRECTORY_MODE, parents=True, exist_ok=True)
    report_path = into / f"{machine_name}.txt"
    ssh.run_into_file(
        runner, address, READ_SCRIPT_FROM_STDIN, report_path, stdin=SCRIPT
    )
    return report_path

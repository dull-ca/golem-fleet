from collections.abc import Callable

from golem_fleet.execution import ports
from golem_fleet.operations import ssh

LOAD_LINES = (
    "set -eu",
    'release="$(uname -r)"',
    'kexec --load "/boot/vmlinuz-$release" \\',
    '    --initrd="/boot/initrd.img-$release" \\',
    "    --reuse-cmdline",
    'test "$(cat /sys/kernel/kexec_loaded)" = 1',
)
LOAD_SCRIPT = "\n".join(LOAD_LINES)
ENTER_SCRIPT = "exec systemctl kexec"
SUCCEEDED_EXIT_CODE = 0


def enter(
    runner: ports.Runner,
    address: str,
    *,
    before_entering: Callable[[], None],
) -> int:
    loaded = ssh.run(runner, address, LOAD_SCRIPT)
    if loaded != SUCCEEDED_EXIT_CODE:
        return loaded
    before_entering()
    ssh.run(runner, address, ENTER_SCRIPT)
    return SUCCEEDED_EXIT_CODE

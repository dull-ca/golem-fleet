import base64
from dataclasses import dataclass

from golem_fleet.fault import Fault
from golem_fleet.fleet import machines

HEADER = "#cloud-config"
REINSTALL_GENERATION_PREFIX = "# golem-fleet-reinstall-generation: "
TOKEN_PATH = "/etc/golem/token"
SECRET_KEY_PATH = "/etc/golem/secret-key"
GOLEM_UNIT = "golemd.service"


class AuthTokenIsEmpty(Fault):
    pass


class SecretKeyIsEmpty(Fault):
    pass


@dataclass(frozen=True)
class Credentials:
    auth_token: str
    secret_key: str

    def __post_init__(self) -> None:
        if not self.auth_token.strip():
            raise AuthTokenIsEmpty
        if not self.secret_key.strip():
            raise SecretKeyIsEmpty


def base64_of(value: str) -> str:
    return base64.b64encode(value.encode()).decode("ascii")


def write_file_lines(path: str, content: str) -> tuple[str, ...]:
    return (
        f"  - path: {path}",
        "    owner: root:root",
        '    permissions: "0600"',
        "    encoding: b64",
        f"    content: {content}",
    )


def reinstall_generation_lines(
    reinstall: machines.ReinstallPolicy,
) -> tuple[str, ...]:
    if isinstance(reinstall, machines.ReinstallRequested):
        return (REINSTALL_GENERATION_PREFIX + str(reinstall.generation),)
    return ()


def render(credentials: Credentials, reinstall: machines.ReinstallPolicy) -> str:
    lines = [
        HEADER,
        *reinstall_generation_lines(reinstall),
        "write_files:",
        *write_file_lines(TOKEN_PATH, base64_of(credentials.auth_token)),
        *write_file_lines(SECRET_KEY_PATH, base64_of(credentials.secret_key)),
        "runcmd:",
        f"  - [systemctl, start, {GOLEM_UNIT}]",
    ]
    return "\n".join(lines) + "\n"

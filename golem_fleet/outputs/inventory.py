from dataclasses import dataclass

from golem_fleet.addresses import source
from golem_fleet.fleet import placements

SSH_ACCOUNT = "root"
TOML_STRING_ESCAPES = (("\\", "\\\\"), ('"', '\\"'))


@dataclass(frozen=True)
class Host:
    name: str
    ssh: str


def escape_toml_string(value: str) -> str:
    escaped = value
    for character, replacement in TOML_STRING_ESCAPES:
        escaped = escaped.replace(character, replacement)
    return escaped


def host_table(host: Host) -> str:
    return f'[hosts.{host.name}]\nssh = "{escape_toml_string(host.ssh)}"'


def hosts(fleet: placements.Fleet, addresses: source.Addresses) -> tuple[Host, ...]:
    return tuple(
        Host(
            name=machine.name,
            ssh=f"{SSH_ACCOUNT}@{source.for_machine(addresses, machine.name).ipv4}",
        )
        for machine in fleet.machines
    )


def render(fleet: placements.Fleet, addresses: source.Addresses) -> str:
    tables = tuple(host_table(host) for host in hosts(fleet, addresses))
    if not tables:
        return ""
    return "\n\n".join(tables) + "\n"

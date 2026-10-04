import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from golem_fleet.execution import ports
from golem_fleet.fault import Fault


class MachineAddressWithoutIpv4(Fault):
    pass


class MachineNeverDeployed(Fault):
    pass


class MachineAddressDeclaredTwice(Fault):
    pass


class Unavailable(Fault):
    pass


class AddressDocumentMalformed(Fault):
    pass


class MachineAddressMalformed(Fault):
    pass


@dataclass(frozen=True)
class MachineAddresses:
    ipv4: str
    ipv6: str | None = None

    def __post_init__(self) -> None:
        if not self.ipv4:
            raise MachineAddressWithoutIpv4(self.ipv6)


Addresses = Mapping[str, MachineAddresses]
Declaration = MachineAddresses | str | Mapping[str, str]


class Source(Protocol):
    def resolve(self, runner: ports.Runner) -> Addresses: ...


def read_address(machine_name: str, declared: object) -> MachineAddresses:
    if isinstance(declared, MachineAddresses):
        return declared
    if isinstance(declared, str):
        return MachineAddresses(ipv4=declared)
    fields = declared if isinstance(declared, Mapping) else {}
    ipv4 = fields.get("ipv4")
    ipv6 = fields.get("ipv6")
    if not isinstance(ipv4, str) or not isinstance(ipv6, str | None):
        raise MachineAddressMalformed(machine_name, declared)
    return MachineAddresses(ipv4=ipv4, ipv6=ipv6)


def read_every_machine(document: object) -> Addresses:
    if not isinstance(document, Mapping):
        raise AddressDocumentMalformed(document)
    read: dict[str, MachineAddresses] = {}
    for machine_name, declared in document.items():
        if not isinstance(machine_name, str):
            raise AddressDocumentMalformed(machine_name)
        read[machine_name] = read_address(machine_name, declared)
    return read


@dataclass(frozen=True)
class Declared:
    mapping: Mapping[str, Declaration]
    machines: Addresses = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "machines", read_every_machine(self.mapping))

    def resolve(self, runner: ports.Runner) -> Addresses:
        del runner
        return self.machines


def resolve_all(sources: Sequence[Source], runner: ports.Runner) -> Addresses:
    merged: dict[str, MachineAddresses] = {}
    for declaring in sources:
        for machine_name, resolved in declaring.resolve(runner).items():
            already_declared = merged.get(machine_name)
            if already_declared is not None:
                raise MachineAddressDeclaredTwice(
                    machine_name, already_declared, resolved
                )
            merged[machine_name] = resolved
    return merged


def decoded_address_document(printed: str) -> dict[str, object]:
    try:
        document = json.loads(printed)
    except json.JSONDecodeError as undecodable:
        raise AddressDocumentMalformed(printed) from undecodable
    if not isinstance(document, dict):
        raise AddressDocumentMalformed(document)
    return document


def for_machine(addresses: Addresses, machine_name: str) -> MachineAddresses:
    found = addresses.get(machine_name)
    if found is None:
        raise MachineNeverDeployed(machine_name)
    return found

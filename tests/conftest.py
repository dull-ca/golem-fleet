from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict, Unpack

import pytest

from golem_fleet.addresses import source
from golem_fleet.cli import machine_commands
from golem_fleet.cli.program import FleetProgram
from golem_fleet.fleet import components, machines, placements
from golem_fleet.outputs import files
from golem_fleet.secrets import refresh, secretspec

OVH_MACHINE = "dull-01"
STATIC_MACHINE = "dev-01"
OVH_SERVICE = "ns5009.ip-1-2-3.net"
OVH_IPV4 = "203.0.113.4"
OVH_IPV6 = "2001:db8::4"
STATIC_IPV4 = "203.0.113.9"
INGRESS_COMPONENT = "ingress"
SITE_COMPONENT = "www-lakin-ca"
SITE_CANONICAL = "www.lakin.ca"
SITE_REDIRECT = "lakin.ca"
DOCS_COMPONENT = "golem-docs"
DOCS_HOSTNAME = "golem-docs.sa-partner.com"
WELL_FORMED_FLEET_KEY = "ab" * 64
MALFORMED_FLEET_KEY = "not-a-fleet-key"
OVH_SUCCESS_STATUS = 200
REGISTRY_HOST = "registry.example.test"
REGISTRY_AUTH_VARIABLE = "GOLEM_REGISTRY_AUTH"
PULL_CREDENTIALS_OUTPUT = "registryPullCredentials"
MACHINE_WITHOUT_OVH = "dev-02"
PLACEMENT_FILENAME = "Placement.emet"


class ProgramFields(TypedDict, total=False):
    addresses: tuple[source.Source, ...]
    artifacts: tuple[files.Artifact, ...]
    generated: Path
    passthrough: str | None
    registry_host: str | None
    registry_auth_variable: str | None
    pull_credentials_output: str | None
    secrets: secretspec.SecretsPolicy | None
    entry_module: str | None
    help: str | None
    program_name: str
    secret_entries: Mapping[str, refresh.SecretEntry]


def ovh_machine(
    *, reinstall: machines.ReinstallPolicy | None = None
) -> machines.Machine:
    install = machines.ImageInstall(
        url="https://images.example.com/nixos.raw",
        checksum="0" * 64,
        checksum_type="sha256",
        efi_bootloader_path=r"\efi\boot\bootx64.efi",
    )
    return machines.Machine(
        OVH_MACHINE,
        machines.OvhBareMetal(
            service_name=OVH_SERVICE,
            install=install,
            reinstall=machines.ProtectedFromReinstall()
            if reinstall is None
            else reinstall,
        ),
    )


def static_machine() -> machines.Machine:
    return machines.Machine(STATIC_MACHINE)


def two_machine_fleet() -> placements.Fleet:
    builder = placements.Builder()
    builder.place(
        ovh_machine(),
        components.workload(INGRESS_COMPONENT),
        components.service(SITE_COMPONENT, hostnames=[SITE_CANONICAL, SITE_REDIRECT]),
    )
    builder.place(
        static_machine(), components.service(DOCS_COMPONENT, hostnames=[DOCS_HOSTNAME])
    )
    return builder.fleet()


def render_machine_names(resolved: files.ResolvedFleet) -> str:
    return "".join(f"{machine.name}\n" for machine in resolved.fleet.machines)


def declared_artifacts() -> tuple[files.Artifact, ...]:
    return (files.Artifact(PLACEMENT_FILENAME, render_machine_names),)


def every_address() -> tuple[source.Source, ...]:
    return (
        source.Declared({OVH_MACHINE: source.MachineAddresses(OVH_IPV4, OVH_IPV6)}),
        source.Declared({STATIC_MACHINE: source.MachineAddresses(STATIC_IPV4)}),
    )


def only_the_ovh_address() -> tuple[source.Source, ...]:
    return (
        source.Declared({OVH_MACHINE: source.MachineAddresses(OVH_IPV4, OVH_IPV6)}),
    )


def fleet_program(**fields: Unpack[ProgramFields]) -> FleetProgram:
    declared: ProgramFields = {
        "addresses": every_address(),
        "artifacts": declared_artifacts(),
        **fields,
    }
    return FleetProgram(fleet=two_machine_fleet(), **declared)


def program_without_bare_metal() -> FleetProgram:
    builder = placements.Builder()
    builder.place(
        machines.Machine(MACHINE_WITHOUT_OVH),
        components.service("web", hostnames=[f"{MACHINE_WITHOUT_OVH}.example.test"]),
    )
    return FleetProgram(
        fleet=builder.fleet(),
        addresses=every_address(),
        artifacts=declared_artifacts(),
    )


@dataclass
class ScriptedOvhTransport:
    answers: dict[str, tuple[int, str]] = field(default_factory=dict)
    requested: list[str] = field(default_factory=list)

    def send(
        self, method: str, url: str, headers: Mapping[str, str], body: str | None
    ) -> tuple[int, str]:
        del method, headers, body
        self.requested.append(url)
        for suffix, answer in self.answers.items():
            if url.endswith(suffix):
                return answer
        return (404, "")


def ovh_transport_answering(answers: Mapping[str, str]) -> ScriptedOvhTransport:
    return ScriptedOvhTransport(
        answers={
            "/auth/time": (OVH_SUCCESS_STATUS, "1700000000"),
            **{path: (OVH_SUCCESS_STATUS, body) for path, body in answers.items()},
        }
    )


def declare_ovh_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(fleet_program().ovh_endpoint_variable, "ovh-ca")
    monkeypatch.setenv(machine_commands.OVH_APPLICATION_KEY_VARIABLE, "application-key")
    monkeypatch.setenv(machine_commands.OVH_APPLICATION_SECRET_VARIABLE, "a-secret")
    monkeypatch.setenv(machine_commands.OVH_CONSUMER_KEY_VARIABLE, "consumer-key")

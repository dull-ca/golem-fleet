from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from golem_fleet.fault import Fault
from golem_fleet.fleet.hostnames import Answering, Hostname, Internal, Published


class Kind(Enum):
    SERVICE = "Service"
    WORKLOAD = "Workload"
    JOB = "Job"

    @property
    def constructor(self) -> str:
        return self.value


class EmptyName(Fault):
    pass


class ServiceAnswersNoHostname(Fault):
    pass


class HostnamesOnlyForService(Fault):
    pass


@dataclass(frozen=True)
class Component:
    kind: Kind
    name: str
    answering: Answering

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise EmptyName(self.name)
        if self.kind is Kind.SERVICE and isinstance(self.answering, Internal):
            raise ServiceAnswersNoHostname(self.name)
        if self.kind is not Kind.SERVICE and isinstance(self.answering, Published):
            raise HostnamesOnlyForService(
                self.name,
                self.kind.constructor,
                self.answering.canonical.text,
            )

    @property
    def hostnames(self) -> tuple[Hostname, ...]:
        return self.answering.hostnames


def answering_hostnames(name: str, texts: Sequence[str]) -> Published:
    if not texts:
        raise ServiceAnswersNoHostname(name)
    canonical, *redirected_from = texts
    return Published(
        Hostname(canonical),
        tuple(Hostname(text) for text in redirected_from),
    )


def service(name: str, *, hostnames: Sequence[str]) -> Component:
    return Component(
        kind=Kind.SERVICE,
        name=name,
        answering=answering_hostnames(name, hostnames),
    )


def workload(name: str) -> Component:
    return Component(kind=Kind.WORKLOAD, name=name, answering=Internal())


def job(name: str) -> Component:
    return Component(kind=Kind.JOB, name=name, answering=Internal())

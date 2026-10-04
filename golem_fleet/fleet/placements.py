from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field

from golem_fleet.fault import Fault
from golem_fleet.fleet.components import Component
from golem_fleet.fleet.hostnames import Hostname, Published
from golem_fleet.fleet.machines import Machine


class MachinePlacesNoComponent(Fault):
    pass


class MachinePlacedTwice(Fault):
    pass


class ComponentNameClaimedTwice(Fault):
    pass


class RouterNameClaimedTwice(Fault):
    pass


class CanonicalHostnameClaimedTwice(Fault):
    pass


class RedirectTargetIsNotCanonical(Fault):
    pass


class MachineIsNotInTheFleet(Fault):
    pass


@dataclass(frozen=True)
class Placement:
    machine: Machine
    components: tuple[Component, ...]

    def __post_init__(self) -> None:
        if not self.components:
            raise MachinePlacesNoComponent(self.machine.name)


def published_components(
    placements: Sequence[Placement],
) -> Iterator[tuple[str, Published]]:
    for placement in placements:
        for component in placement.components:
            if isinstance(component.answering, Published):
                yield component.name, component.answering


def reject_machine_placed_twice(placements: Sequence[Placement]) -> None:
    placed: set[str] = set()
    for placement in placements:
        if placement.machine.name in placed:
            raise MachinePlacedTwice(placement.machine.name)
        placed.add(placement.machine.name)


def reject_component_named_twice_on_a_machine(placements: Sequence[Placement]) -> None:
    for placement in placements:
        claimed: set[str] = set()
        for component in placement.components:
            if component.name in claimed:
                raise ComponentNameClaimedTwice(placement.machine.name, component.name)
            claimed.add(component.name)


def reject_router_name_claimed_twice_on_a_machine(
    placements: Sequence[Placement],
) -> None:
    for placement in placements:
        claimed: dict[str, Hostname] = {}
        for component in placement.components:
            for hostname in component.hostnames:
                if hostname.router in claimed:
                    raise RouterNameClaimedTwice(
                        placement.machine.name,
                        claimed[hostname.router].text,
                        hostname.text,
                        hostname.router,
                    )
                claimed[hostname.router] = hostname


def reject_canonical_hostname_claimed_twice(placements: Sequence[Placement]) -> None:
    claimed: dict[str, str] = {}
    for name, answering in published_components(placements):
        canonical = answering.canonical.text
        if canonical in claimed:
            raise CanonicalHostnameClaimedTwice(canonical, claimed[canonical], name)
        claimed[canonical] = name


def reject_redirect_target_that_is_canonical(placements: Sequence[Placement]) -> None:
    canonical_of: dict[str, str] = {}
    redirect_of: dict[str, str] = {}
    for name, answering in published_components(placements):
        canonical_of.setdefault(answering.canonical.text, name)
        for redirect in answering.redirected_from:
            redirect_of.setdefault(redirect.text, name)
    for hostname, redirecting in redirect_of.items():
        canonical = canonical_of.get(hostname)
        if canonical is not None:
            raise RedirectTargetIsNotCanonical(hostname, redirecting, canonical)


@dataclass(frozen=True)
class PublishedHostname:
    hostname: Hostname
    machine_name: str
    component_name: str
    redirects_to: Hostname | None = None

    @property
    def is_canonical(self) -> bool:
        return self.redirects_to is None


@dataclass(frozen=True)
class Fleet:
    placements: tuple[Placement, ...]

    def __post_init__(self) -> None:
        reject_machine_placed_twice(self.placements)
        reject_component_named_twice_on_a_machine(self.placements)
        reject_router_name_claimed_twice_on_a_machine(self.placements)
        reject_canonical_hostname_claimed_twice(self.placements)
        reject_redirect_target_that_is_canonical(self.placements)

    @property
    def machines(self) -> tuple[Machine, ...]:
        return tuple(placement.machine for placement in self.placements)

    @property
    def carries_ovh_bare_metal(self) -> bool:
        return any(machine.ovh is not None for machine in self.machines)

    @property
    def components(self) -> tuple[Component, ...]:
        return tuple(
            component
            for placement in self.placements
            for component in placement.components
        )

    @property
    def components_by_machine(self) -> Mapping[str, tuple[Component, ...]]:
        return {
            placement.machine.name: placement.components
            for placement in self.placements
        }

    def machine_named(self, name: str) -> Machine:
        for machine in self.machines:
            if machine.name == name:
                return machine
        raise MachineIsNotInTheFleet(name, tuple(m.name for m in self.machines))

    @property
    def published_hostnames(self) -> tuple[PublishedHostname, ...]:
        published: list[PublishedHostname] = []
        for placement in self.placements:
            for component in placement.components:
                answering = component.answering
                if not isinstance(answering, Published):
                    continue
                canonical = answering.canonical
                published.extend(
                    PublishedHostname(
                        hostname=hostname,
                        machine_name=placement.machine.name,
                        component_name=component.name,
                        redirects_to=None if hostname == canonical else canonical,
                    )
                    for hostname in answering.hostnames
                )
        return tuple(published)


@dataclass
class Builder:
    placements: list[Placement] = field(default_factory=list)

    def place(self, machine: Machine, *components: Component) -> Placement:
        placement = Placement(machine, components)
        self.placements.append(placement)
        return placement

    def fleet(self) -> Fleet:
        return Fleet(tuple(self.placements))

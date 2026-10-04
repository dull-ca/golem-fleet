from collections.abc import Callable

import pytest

from golem_fleet.fault import Fault
from golem_fleet.fleet import components, hostnames, machines, placements

DEV = machines.Machine("dev-01")
DULL = machines.Machine("dull-01")
IMPLEMUS = components.service("implemus", hostnames=["implemus.sa-partner.com"])
BACKUP = components.workload("backup")
LAKIN = components.service("lakin", hostnames=["www.lakin.ca", "lakin.ca"])
MIGRATE = components.job("migrate")


def placing(
    machine: machines.Machine, *placed: components.Component
) -> placements.Placement:
    return placements.Placement(machine, placed)


def service_answering(
    name: str, answering: hostnames.Published
) -> components.Component:
    return components.Component(
        kind=components.Kind.SERVICE,
        name=name,
        answering=answering,
    )


def refusal(
    declare: Callable[[], object],
) -> tuple[type[Fault], tuple[object, ...]]:
    with pytest.raises(Fault) as raised:
        declare()
    return type(raised.value), raised.value.args


def test_the_builder_returns_each_placement_and_the_fleet_names_its_own() -> None:
    builder = placements.Builder()

    first = builder.place(DEV, IMPLEMUS, BACKUP)
    builder.place(DULL, LAKIN, MIGRATE)
    fleet = builder.fleet()

    assert first == placing(DEV, IMPLEMUS, BACKUP)
    assert fleet.machines == (DEV, DULL)
    assert fleet.components == (IMPLEMUS, BACKUP, LAKIN, MIGRATE)
    assert fleet.machine_named("dull-01") is DULL
    assert refusal(lambda: fleet.machine_named("dev-02")) == (
        placements.MachineIsNotInTheFleet,
        ("dev-02", ("dev-01", "dull-01")),
    )


def test_a_fleet_that_breaks_a_rule_is_rejected_naming_what_broke_it() -> None:
    placed_twice = (placing(DEV, BACKUP), placing(DEV, MIGRATE))
    named_twice = (placing(DEV, BACKUP, components.workload("backup")),)
    routers = (
        placing(
            DEV,
            components.service("dashed", hostnames=["a-b.com"]),
            components.service("dotted", hostnames=["a.b.com"]),
        ),
    )
    claimed = (
        placing(DEV, components.service("implemus", hostnames=["www.lakin.ca"])),
        placing(DULL, LAKIN),
    )
    redirected = (
        placing(DEV, LAKIN),
        placing(DULL, components.service("legacy", hostnames=["lakin.ca"])),
    )

    assert refusal(lambda: placing(DEV)) == (
        placements.MachinePlacesNoComponent,
        ("dev-01",),
    )
    assert refusal(lambda: placements.Fleet(placed_twice)) == (
        placements.MachinePlacedTwice,
        ("dev-01",),
    )
    assert refusal(lambda: placements.Fleet(named_twice)) == (
        placements.ComponentNameClaimedTwice,
        ("dev-01", "backup"),
    )
    assert refusal(lambda: placements.Fleet(routers)) == (
        placements.RouterNameClaimedTwice,
        ("dev-01", "a-b.com", "a.b.com", "a-b-com"),
    )
    assert refusal(lambda: placements.Fleet(claimed)) == (
        placements.CanonicalHostnameClaimedTwice,
        ("www.lakin.ca", "implemus", "lakin"),
    )
    assert refusal(lambda: placements.Fleet(redirected)) == (
        placements.RedirectTargetIsNotCanonical,
        ("lakin.ca", "lakin", "legacy"),
    )


def test_two_components_answering_one_hostname_object_are_rejected() -> None:
    shared = hostnames.Published(hostnames.Hostname("a.b.com"))
    placement = placing(
        DEV,
        service_answering("first", shared),
        service_answering("second", shared),
    )

    assert refusal(lambda: placements.Fleet((placement,))) == (
        placements.RouterNameClaimedTwice,
        ("dev-01", "a.b.com", "a.b.com", "a-b-com"),
    )


def test_one_component_and_two_components_sharing_a_name_may_span_machines() -> None:
    metrics = components.workload("metrics")

    shared = placements.Fleet((placing(DEV, metrics), placing(DULL, metrics)))
    named_twice = placements.Fleet(
        (
            placing(DEV, components.workload("metrics")),
            placing(DULL, components.job("metrics")),
        )
    )

    assert shared.components == (metrics, metrics)
    assert [one.kind for one in named_twice.components] == [
        components.Kind.WORKLOAD,
        components.Kind.JOB,
    ]

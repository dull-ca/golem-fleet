from collections.abc import Callable

import pytest

from golem_fleet.fault import Fault
from golem_fleet.fleet import components, hostnames

BARE_COMPONENTS = (components.workload("backup"), components.job("migrate"))


def component_answering(
    kind: components.Kind, name: str, answering: hostnames.Answering
) -> components.Component:
    return components.Component(kind=kind, name=name, answering=answering)


def refusal(
    declare: Callable[[], object],
) -> tuple[type[Fault], tuple[object, ...]]:
    with pytest.raises(Fault) as raised:
        declare()
    return type(raised.value), raised.value.args


def test_each_factory_declares_its_kind_and_its_answering() -> None:
    site = components.service("implemus", hostnames=["www.lakin.ca"])

    assert (site.kind, site.answering) == (
        components.Kind.SERVICE,
        hostnames.published("www.lakin.ca"),
    )
    assert [(one.kind, one.answering) for one in BARE_COMPONENTS] == [
        (components.Kind.WORKLOAD, hostnames.Internal()),
        (components.Kind.JOB, hostnames.Internal()),
    ]
    assert BARE_COMPONENTS[0].hostnames == ()


def test_a_component_that_answers_the_wrong_way_is_rejected() -> None:
    no_hostname = (components.ServiceAnswersNoHostname, ("implemus",))

    assert refusal(lambda: components.service("implemus", hostnames=[])) == no_hostname
    assert (
        refusal(
            lambda: component_answering(
                components.Kind.SERVICE, "implemus", hostnames.Internal()
            )
        )
        == no_hostname
    )
    assert refusal(
        lambda: component_answering(
            components.Kind.WORKLOAD, "backup", hostnames.published("www.lakin.ca")
        )
    ) == (components.HostnamesOnlyForService, ("backup", "Workload", "www.lakin.ca"))


def test_an_unusable_name_is_rejected() -> None:
    assert refusal(lambda: components.workload("   ")) == (
        components.EmptyName,
        ("   ",),
    )

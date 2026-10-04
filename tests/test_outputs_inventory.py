import pytest

from golem_fleet.addresses import source
from golem_fleet.fleet import components, machines, placements
from golem_fleet.outputs import inventory

RUNNER = components.workload("runner")
TWO_MACHINE_FLEET = placements.Fleet(
    (
        placements.Placement(machines.Machine("dev-01"), (RUNNER,)),
        placements.Placement(
            machines.Machine("dull-01"), (components.workload("archivist"),)
        ),
    )
)
DEV_ADDRESS = source.MachineAddresses("203.0.113.7")
DULL_ADDRESS = source.MachineAddresses("198.51.100.4")
ADDRESSES = {"dev-01": DEV_ADDRESS, "dull-01": DULL_ADDRESS}
BARE_INVENTORY = """[hosts.dev-01]
ssh = "root@203.0.113.7"

[hosts.dull-01]
ssh = "root@198.51.100.4"
"""


def test_an_inventory_table_follows_the_fleet_order_naming_each_destination() -> None:
    reversed_addresses = {"dull-01": DULL_ADDRESS, "dev-01": DEV_ADDRESS}

    assert inventory.render(TWO_MACHINE_FLEET, ADDRESSES) == BARE_INVENTORY
    assert inventory.render(TWO_MACHINE_FLEET, reversed_addresses) == BARE_INVENTORY


def test_inventory_rejects_a_machine_the_addresses_never_mention() -> None:
    with pytest.raises(source.MachineNeverDeployed) as raised:
        inventory.render(TWO_MACHINE_FLEET, {"dev-01": DEV_ADDRESS})

    assert raised.value.args == ("dull-01",)


def test_every_emitted_toml_string_escapes_a_backslash_and_a_quote() -> None:
    quoting_fleet = placements.Fleet(
        (placements.Placement(machines.Machine("odd-01"), (RUNNER,)),)
    )
    quoting_addresses = {"odd-01": source.MachineAddresses('203.0.113.7" ok \\ ok')}

    rendered = inventory.render(quoting_fleet, quoting_addresses)

    assert inventory.escape_toml_string('a\\b"c') == 'a\\\\b\\"c'
    assert 'ssh = "root@203.0.113.7\\" ok \\\\ ok"' in rendered


def test_a_fleet_that_places_no_machine_renders_an_empty_inventory() -> None:
    assert inventory.render(placements.Fleet(()), {}) == ""

from pathlib import Path

from golem_fleet.addresses import source
from golem_fleet.fleet import components, machines, placements
from golem_fleet.outputs import files, inventory

IMPLEMUS = components.service("implemus", hostnames=["implemus.sa-partner.com"])
SMALL_FLEET = placements.Fleet(
    (placements.Placement(machines.Machine("dev-01"), (IMPLEMUS,)),)
)
ADDRESSES = {"dev-01": source.MachineAddresses("203.0.113.7")}
PLACEMENT_TEXT = "module Placement exposing (hosts)\n"
PLACEMENT_FILENAME = "Placement.emet"
INVENTORY_FILENAME = "fleet.toml"


class RecordingRenderer:
    asked_about: files.ResolvedFleet | None = None

    def __call__(self, resolved: files.ResolvedFleet) -> str:
        self.asked_about = resolved
        return PLACEMENT_TEXT


def test_a_declared_artifact_is_written_at_its_filename_from_the_resolved_fleet(
    tmp_path: Path,
) -> None:
    renderer = RecordingRenderer()
    declared = (files.Artifact(PLACEMENT_FILENAME, renderer),)
    into = tmp_path / "missing" / "generated"

    written = files.write_all(SMALL_FLEET, ADDRESSES, declared=declared, into=into)
    (into / PLACEMENT_FILENAME).write_text("stale", encoding="utf-8")
    files.write_all(SMALL_FLEET, ADDRESSES, declared=declared, into=into)

    assert renderer.asked_about == files.ResolvedFleet(SMALL_FLEET, ADDRESSES)
    assert written == (into / INVENTORY_FILENAME, into / PLACEMENT_FILENAME)
    assert [path.read_text(encoding="utf-8") for path in written] == [
        inventory.render(SMALL_FLEET, ADDRESSES),
        PLACEMENT_TEXT,
    ]


def test_the_library_writes_its_inventory_whether_or_not_anything_is_declared(
    tmp_path: Path,
) -> None:
    bare = tmp_path / "bare"
    alongside = tmp_path / "alongside"

    without = files.write_all(SMALL_FLEET, ADDRESSES, declared=(), into=bare)
    with_one = files.write_all(
        SMALL_FLEET,
        ADDRESSES,
        declared=(files.Artifact(PLACEMENT_FILENAME, RecordingRenderer()),),
        into=alongside,
    )

    assert without == (bare / INVENTORY_FILENAME,)
    assert with_one[0] == alongside / INVENTORY_FILENAME
    assert (bare / INVENTORY_FILENAME).read_text(encoding="utf-8") == inventory.render(
        SMALL_FLEET, ADDRESSES
    )

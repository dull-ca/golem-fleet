from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from golem_fleet.addresses import source
from golem_fleet.fleet import placements
from golem_fleet.outputs import inventory

INVENTORY_FILENAME = "fleet.toml"


@dataclass(frozen=True)
class ResolvedFleet:
    fleet: placements.Fleet
    addresses: source.Addresses


@dataclass(frozen=True)
class Artifact:
    filename: str
    render: Callable[[ResolvedFleet], str]


def render_inventory(resolved: ResolvedFleet) -> str:
    return inventory.render(resolved.fleet, resolved.addresses)


LIBRARY_ARTIFACTS = (Artifact(INVENTORY_FILENAME, render_inventory),)


def rendered(
    fleet: placements.Fleet,
    addresses: source.Addresses,
    *,
    declared: Sequence[Artifact],
) -> tuple[tuple[str, str], ...]:
    resolved = ResolvedFleet(fleet, addresses)
    return tuple(
        (artifact.filename, artifact.render(resolved))
        for artifact in (*LIBRARY_ARTIFACTS, *declared)
    )


def write_all(
    fleet: placements.Fleet,
    addresses: source.Addresses,
    *,
    declared: Sequence[Artifact],
    into: Path,
) -> tuple[Path, ...]:
    into.mkdir(parents=True, exist_ok=True)
    written = []
    for filename, content in rendered(fleet, addresses, declared=declared):
        path = into / filename
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return tuple(written)

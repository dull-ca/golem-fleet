from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from golem_fleet.fault import Fault

SECRETS_MATCH_EXIT_CODE = 0
SECRETS_DIFFER_EXIT_CODE = 1
MATCHING_STATE = "matches"
ABSENT_STATE = "absent"
DIFFERING_STATE = "differs"
STORED_STATE = "stored"


class SecretNotMinted(Fault):
    pass


class MintedSecretNotAString(Fault):
    pass


type MintedSecretTransform = Callable[[object], str]


@dataclass(frozen=True)
class TransformedEntry:
    entry: str
    transform: MintedSecretTransform


type SecretEntry = str | TransformedEntry


def entry_name(entry: SecretEntry) -> str:
    return entry if isinstance(entry, str) else entry.entry


def entry_transform(entry: SecretEntry) -> MintedSecretTransform | None:
    return None if isinstance(entry, str) else entry.transform


@dataclass(frozen=True)
class SecretComparison:
    name: str
    entry: str
    matches: bool
    present: bool
    transform: MintedSecretTransform | None = None


def minted_secret(
    outputs: Mapping[str, object],
    name: str,
    transform: MintedSecretTransform | None = None,
) -> str:
    if name not in outputs:
        raise SecretNotMinted(name, *sorted(outputs))
    minted = outputs[name]
    if transform is not None:
        return transform(minted)
    if not isinstance(minted, str):
        raise MintedSecretNotAString(name, type(minted).__name__)
    return minted


def compared_secret(
    outputs: Mapping[str, object],
    environment: Mapping[str, str],
    name: str,
    entry: SecretEntry,
) -> SecretComparison:
    transform = entry_transform(entry)
    minted = minted_secret(outputs, name, transform)
    held = environment.get(entry_name(entry), "")
    return SecretComparison(
        name=name,
        entry=entry_name(entry),
        matches=bool(held) and held == minted,
        present=bool(held),
        transform=transform,
    )


def compare_secrets(
    outputs: Mapping[str, object],
    environment: Mapping[str, str],
    mapping: Mapping[str, SecretEntry],
) -> tuple[SecretComparison, ...]:
    return tuple(
        compared_secret(outputs, environment, name, entry)
        for name, entry in mapping.items()
    )


def secret_state(comparison: SecretComparison) -> str:
    if comparison.matches:
        return MATCHING_STATE
    return DIFFERING_STATE if comparison.present else ABSENT_STATE


def check_exit_code(
    comparisons: Sequence[SecretComparison], report: Callable[[str], None]
) -> int:
    for comparison in comparisons:
        report(f"{comparison.entry} {secret_state(comparison)}")
    if all(comparison.matches for comparison in comparisons):
        return SECRETS_MATCH_EXIT_CODE
    return SECRETS_DIFFER_EXIT_CODE


def store_secrets(
    comparisons: Sequence[SecretComparison],
    outputs: Mapping[str, object],
    store: Callable[[str, str], None],
    report: Callable[[str], None],
) -> int:
    for comparison in comparisons:
        if comparison.matches:
            report(f"{comparison.entry} {MATCHING_STATE}")
            continue
        store(
            comparison.entry,
            minted_secret(outputs, comparison.name, comparison.transform),
        )
        report(f"{comparison.entry} {STORED_STATE}")
    return SECRETS_MATCH_EXIT_CODE

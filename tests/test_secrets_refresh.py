import json

import pytest

from golem_fleet.secrets import refresh, registry_auth

MINTED_KEY = "ab" * 64
MINTED_AUTH = "Z29sZW06cHVsbA=="
STALE_AUTH = "b3V0LW9mLWRhdGU="
EVERY_SECRET_VALUE = (MINTED_KEY, MINTED_AUTH, STALE_AUTH)
OUTPUTS: dict[str, object] = {
    "fleetSecretKey": MINTED_KEY,
    "registryPullAuth": MINTED_AUTH,
}
MAPPING = {"fleetSecretKey": "golem_key", "registryPullAuth": "registry_auth"}
HELD_MATCHING = {"golem_key": MINTED_KEY, "registry_auth": MINTED_AUTH}
HELD_STALE = {"golem_key": MINTED_KEY, "registry_auth": STALE_AUTH}
HELD_NO_KEY = {"golem_key": "", "registry_auth": MINTED_AUTH}
REGISTRY_HOST = "registry.example.test"
PULL_CREDENTIALS_OUTPUT = "registryPullCredentials"
PULL_AUTH_ENTRY = "STRABS_REGISTRY_PULL_AUTH"
DOCKER_CONFIG = json.dumps({"auths": {REGISTRY_HOST: {"auth": MINTED_AUTH}}})
PULL_CREDENTIALS_OUTPUTS: dict[str, object] = {PULL_CREDENTIALS_OUTPUT: DOCKER_CONFIG}


def reported_lines(states: tuple[str, ...]) -> list[str]:
    return [
        f"{entry} {state}"
        for entry, state in zip(MAPPING.values(), states, strict=True)
    ]


@pytest.mark.parametrize(
    ("held", "expected"),
    [
        (HELD_MATCHING, ((True, True), (True, True))),
        (HELD_STALE, ((True, True), (True, False))),
        ({}, ((False, False), (False, False))),
        (HELD_NO_KEY, ((False, False), (True, True))),
    ],
)
def test_every_held_secret_is_compared_without_carrying_a_secret_value(
    held: dict[str, str], expected: tuple[tuple[bool, bool], ...]
) -> None:
    compared = refresh.compare_secrets(OUTPUTS, held, MAPPING)

    assert tuple((one.present, one.matches) for one in compared) == expected
    assert tuple(one.name for one in compared) == tuple(MAPPING)
    assert tuple(one.entry for one in compared) == tuple(MAPPING.values())
    assert all(value not in repr(compared) for value in EVERY_SECRET_VALUE)


def test_a_secret_never_minted_or_minted_as_another_type_is_rejected() -> None:
    with pytest.raises(refresh.SecretNotMinted) as missing:
        refresh.compare_secrets(OUTPUTS, {}, {"fleetSigningKey": "golem_signing_key"})

    assert missing.value.args == (
        "fleetSigningKey",
        "fleetSecretKey",
        "registryPullAuth",
    )

    with pytest.raises(refresh.MintedSecretNotAString) as wrong_type:
        refresh.compare_secrets({"fleetSecretKey": 7}, {}, {"fleetSecretKey": "entry"})

    assert wrong_type.value.args == ("fleetSecretKey", "int")


@pytest.mark.parametrize(
    ("held", "expected_exit_code", "expected_states"),
    [
        (HELD_MATCHING, 0, ("matches", "matches")),
        (HELD_STALE, 1, ("matches", "differs")),
        ({}, 1, ("absent", "absent")),
    ],
)
def test_the_check_reports_every_entry_and_exits_on_the_worst_of_them(
    held: dict[str, str],
    expected_exit_code: int,
    expected_states: tuple[str, ...],
) -> None:
    compared = refresh.compare_secrets(OUTPUTS, held, MAPPING)
    lines: list[str] = []

    assert refresh.check_exit_code(compared, lines.append) == expected_exit_code
    assert lines == reported_lines(expected_states)


def test_only_the_differing_secrets_are_stored() -> None:
    compared = refresh.compare_secrets(OUTPUTS, HELD_STALE, MAPPING)
    stored: list[tuple[str, str]] = []
    lines: list[str] = []

    exit_code = refresh.store_secrets(
        compared,
        OUTPUTS,
        lambda entry, value: stored.append((entry, value)),
        lines.append,
    )

    assert exit_code == 0
    assert stored == [("registry_auth", MINTED_AUTH)]
    assert lines == reported_lines(("matches", "stored"))


def lifted_pull_auth(minted: object) -> str:
    return registry_auth.pull_auth(minted, registry_host=REGISTRY_HOST)


def pull_auth_entries() -> dict[str, refresh.SecretEntry]:
    return {
        PULL_CREDENTIALS_OUTPUT: refresh.TransformedEntry(
            PULL_AUTH_ENTRY, lifted_pull_auth
        )
    }


@pytest.mark.parametrize(
    ("held", "expected_matches"),
    [({PULL_AUTH_ENTRY: MINTED_AUTH}, True), ({PULL_AUTH_ENTRY: STALE_AUTH}, False)],
)
def test_an_entry_transform_is_compared_against_what_the_transform_yields(
    held: dict[str, str], *, expected_matches: bool
) -> None:
    compared = refresh.compare_secrets(
        PULL_CREDENTIALS_OUTPUTS, held, pull_auth_entries()
    )

    assert tuple(one.entry for one in compared) == (PULL_AUTH_ENTRY,)
    assert tuple(one.matches for one in compared) == (expected_matches,)
    assert DOCKER_CONFIG not in repr(compared)


def test_an_entry_transform_stores_the_lifted_value_not_the_whole_document() -> None:
    compared = refresh.compare_secrets(
        PULL_CREDENTIALS_OUTPUTS, {PULL_AUTH_ENTRY: STALE_AUTH}, pull_auth_entries()
    )
    stored: list[tuple[str, str]] = []
    lines: list[str] = []

    exit_code = refresh.store_secrets(
        compared,
        PULL_CREDENTIALS_OUTPUTS,
        lambda entry, value: stored.append((entry, value)),
        lines.append,
    )

    assert exit_code == refresh.SECRETS_MATCH_EXIT_CODE
    assert stored == [(PULL_AUTH_ENTRY, MINTED_AUTH)]
    assert lines == [f"{PULL_AUTH_ENTRY} {refresh.STORED_STATE}"]

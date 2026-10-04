import json

import pytest

from golem_fleet.secrets import registry_auth

REGISTRY_HOST = "registry.dull.ca"
PULL_AUTH = "Z29sZW06cHVsbA=="
DOCKER_CONFIG = json.dumps({"auths": {REGISTRY_HOST: {"auth": PULL_AUTH}}})
ANOTHER_HOST = json.dumps({"auths": {"registry.example.com": {"auth": PULL_AUTH}}})
WITHOUT_AN_AUTH = json.dumps({"auths": {REGISTRY_HOST: {"identitytoken": "x"}}})
WITH_AN_EMPTY_AUTH = json.dumps({"auths": {REGISTRY_HOST: {"auth": ""}}})


def test_the_auth_is_read_out_of_the_docker_config() -> None:
    assert (
        registry_auth.pull_auth(DOCKER_CONFIG, registry_host=REGISTRY_HOST) == PULL_AUTH
    )


def refusal_of(credential: object) -> tuple[object, ...]:
    with pytest.raises(registry_auth.Unrecognised) as raised:
        registry_auth.pull_auth(credential, registry_host=REGISTRY_HOST)
    return raised.value.args


def test_an_unusable_pull_credential_carries_the_host_and_nothing_else() -> None:
    assert refusal_of({"auths": {}}) == (REGISTRY_HOST,)
    assert refusal_of("not json") == (REGISTRY_HOST,)
    assert refusal_of('{"credsStore": "pass"}') == (REGISTRY_HOST,)
    assert refusal_of("[]") == (REGISTRY_HOST,)
    assert refusal_of(ANOTHER_HOST) == (REGISTRY_HOST,)
    assert refusal_of(WITHOUT_AN_AUTH) == (REGISTRY_HOST,)
    assert refusal_of(WITH_AN_EMPTY_AUTH) == (REGISTRY_HOST,)

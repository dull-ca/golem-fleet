import json

import pytest
from conftest import (
    ScriptedOvhTransport,
    declare_ovh_credentials,
    fleet_program,
    ovh_transport_answering,
)
from typer.testing import CliRunner, Result

from golem_fleet.cli import machine_commands, ovh_commands
from golem_fleet.providers.ovh import api

API_PATH = "/dedicated/server/ns5009.ip-1-2-3.net"
ABSENT_API_PATH = "/dedicated/server/absent"
RESOURCE = {"state": "ok", "datacenter": "bhs1", "commercialRange": "Rise"}
CANADIAN_API_ROOT = "https://ca.api.ovh.com/1.0"


def answering_transport() -> ScriptedOvhTransport:
    return ovh_transport_answering({API_PATH: json.dumps(RESOURCE)})


def ovh_get(path: str, transport: ScriptedOvhTransport) -> Result:
    app = ovh_commands.build(fleet_program(), transport=transport)
    return CliRunner().invoke(app, ["get", path])


def test_get_prints_the_response_indented_and_sorted_at_the_endpoints_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    declare_ovh_credentials(monkeypatch)
    transport = answering_transport()

    result = ovh_get(API_PATH, transport)

    indent = ovh_commands.JSON_INDENT
    assert result.exit_code == 0
    assert result.stdout.rstrip("\n") == json.dumps(
        RESOURCE, indent=indent, sort_keys=True
    )
    assert transport.requested[-1] == f"{CANADIAN_API_ROOT}{API_PATH}"


def test_a_request_the_api_will_not_answer_is_a_named_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    declare_ovh_credentials(monkeypatch)

    absent = ovh_get(ABSENT_API_PATH, answering_transport())
    monkeypatch.delenv(machine_commands.OVH_CONSUMER_KEY_VARIABLE)
    uncredentialed = ovh_get(API_PATH, answering_transport())

    assert absent.exit_code == 1
    assert api.ResourceNotFound.__name__ in absent.stderr
    assert ABSENT_API_PATH in absent.stderr
    assert uncredentialed.exit_code == 1
    assert api.MissingCredential.__name__ in uncredentialed.stderr

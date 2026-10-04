import io
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from email.message import Message

import pytest

from golem_fleet.providers.ovh import api

BASE_URL = "https://eu.api.ovh.com/1.0"
ACCOUNT_PATH = "/me"
ACCOUNT_URL = f"{BASE_URL}{ACCOUNT_PATH}"
SERVER_TIME = 1700000000
LOCAL_TIME = 1699999880
PINNED_SIGNATURE = "$1$155a663609f30a7bb4a6334f43ff008e2b35f8a7"
OK_STATUS = 200
NOT_FOUND_STATUS = 404
SERVER_ERROR_STATUS = 500
ACCOUNT_BODY = '{"nichandle": "ab12345-ovh"}'
MAINTENANCE = "<html>maintenance</html>"
VAGUE_TIME = "half past four"
EXAMPLE_URL = "https://api.example.test/1.0"
UNENCRYPTED_URL = "http://api.example.test/1.0"
REFUSAL = b'{"message": "no such object"}'
EVERY_CREDENTIAL = {
    "endpoint": "ovh-eu",
    "application_key": "app-key",
    "application_secret": "s3cr3t",
    "consumer_key": "consumer",
}
EVERY_ENDPOINT = [("ovh-eu", BASE_URL), (f"{EXAMPLE_URL}/", EXAMPLE_URL)]
REFUSED_CREDENTIALS = [
    ({"endpoint": "ovh-mars"}, api.UnknownEndpoint, ("ovh-mars",)),
    ({"endpoint": UNENCRYPTED_URL}, api.UnknownEndpoint, (UNENCRYPTED_URL,)),
    ({"endpoint": ""}, api.MissingCredential, ("endpoint",)),
    ({"application_key": ""}, api.MissingCredential, ("application key",)),
    ({"application_secret": "   "}, api.MissingCredential, ("application secret",)),
    ({"consumer_key": ""}, api.MissingCredential, ("consumer key",)),
]
REFUSED_ANSWERS = [
    ((NOT_FOUND_STATUS, "{}"), api.ResourceNotFound, (ACCOUNT_PATH,)),
    (
        (SERVER_ERROR_STATUS, "boom"),
        api.RequestFailed,
        (SERVER_ERROR_STATUS, "boom"),
    ),
    ((OK_STATUS, MAINTENANCE), api.ResponseNotJson, (ACCOUNT_PATH, MAINTENANCE)),
]
REFUSED_CLOCK_ANSWERS = [
    ((OK_STATUS, VAGUE_TIME), api.ServerTimeNotUnderstood, (VAGUE_TIME,)),
    (
        (SERVER_ERROR_STATUS, "down"),
        api.RequestFailed,
        (SERVER_ERROR_STATUS, "down"),
    ),
]


@dataclass(frozen=True)
class SentRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: str | None


SIGNED_ACCOUNT_REQUEST = SentRequest(
    method="GET",
    url=ACCOUNT_URL,
    headers={
        "X-Ovh-Application": EVERY_CREDENTIAL["application_key"],
        "X-Ovh-Consumer": EVERY_CREDENTIAL["consumer_key"],
        "X-Ovh-Timestamp": str(SERVER_TIME),
        "X-Ovh-Signature": PINNED_SIGNATURE,
        "Content-Type": "application/json",
    },
    body=None,
)
ASKED_THE_API_CLOCK = SentRequest("GET", f"{BASE_URL}{api.SERVER_TIME_PATH}", {}, None)


@dataclass
class FakeTransport:
    answers: list[tuple[int, str]] = field(default_factory=list)
    clock_answer: tuple[int, str] = (OK_STATUS, str(SERVER_TIME))
    sent: list[SentRequest] = field(default_factory=list)

    def send(
        self, method: str, url: str, headers: Mapping[str, str], body: str | None
    ) -> tuple[int, str]:
        self.sent.append(SentRequest(method, url, dict(headers), body))
        if url.endswith(api.SERVER_TIME_PATH):
            return self.clock_answer
        return self.answers.pop(0)


def credentials(**refused: str) -> api.Credentials:
    return api.Credentials(**{**EVERY_CREDENTIAL, **refused})


def client_for(transport: FakeTransport) -> api.Client:
    return api.Client(credentials(), transport)


def refuse_to_open(request: urllib.request.Request, timeout: float) -> None:
    del request, timeout
    raise urllib.error.HTTPError(
        ACCOUNT_URL, NOT_FOUND_STATUS, "Not Found", Message(), io.BytesIO(REFUSAL)
    )


@pytest.mark.parametrize(("endpoint", "base_url"), EVERY_ENDPOINT)
def test_credentials_resolve_an_endpoint_to_its_base_url(
    endpoint: str, base_url: str
) -> None:
    assert credentials(endpoint=endpoint).base_url == base_url


@pytest.mark.parametrize(("refused", "fault", "expected_args"), REFUSED_CREDENTIALS)
def test_credentials_name_the_endpoint_or_the_credential_they_refuse(
    refused: dict[str, str], fault: type[Exception], expected_args: tuple[object, ...]
) -> None:
    with pytest.raises(fault) as raised:
        credentials(**refused)

    assert raised.value.args == expected_args


def test_signature_is_the_prefixed_sha1_of_the_ovh_payload() -> None:
    assert api.ovh_signature(credentials(), "GET", ACCOUNT_URL, "", SERVER_TIME) == (
        PINNED_SIGNATURE
    )


def test_get_signs_every_request_against_an_api_clock_read_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api, "local_time", lambda: LOCAL_TIME)
    transport = FakeTransport(answers=[(OK_STATUS, ACCOUNT_BODY)] * 2)
    client = client_for(transport)

    assert client.url_for("me") == ACCOUNT_URL
    assert client.get(ACCOUNT_PATH) == {"nichandle": "ab12345-ovh"}
    assert client.get(ACCOUNT_PATH) == {"nichandle": "ab12345-ovh"}
    assert client.time_drift_seconds == SERVER_TIME - LOCAL_TIME
    assert transport.sent == [
        ASKED_THE_API_CLOCK,
        SIGNED_ACCOUNT_REQUEST,
        SIGNED_ACCOUNT_REQUEST,
    ]


@pytest.mark.parametrize(("answer", "fault", "expected_args"), REFUSED_ANSWERS)
def test_get_names_the_answer_it_refuses(
    answer: tuple[int, str], fault: type[Exception], expected_args: tuple[object, ...]
) -> None:
    with pytest.raises(fault) as raised:
        client_for(FakeTransport(answers=[answer])).get(ACCOUNT_PATH)

    assert raised.value.args == expected_args


@pytest.mark.parametrize(("answer", "fault", "expected_args"), REFUSED_CLOCK_ANSWERS)
def test_server_time_names_the_clock_answer_it_refuses(
    answer: tuple[int, str], fault: type[Exception], expected_args: tuple[object, ...]
) -> None:
    with pytest.raises(fault) as raised:
        client_for(FakeTransport(clock_answer=answer)).server_time()

    assert raised.value.args == expected_args


def test_the_urllib_transport_answers_a_refusal_instead_of_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", refuse_to_open)

    assert api.UrllibTransport().send("GET", ACCOUNT_URL, {}, None) == (
        NOT_FOUND_STATUS,
        REFUSAL.decode(),
    )

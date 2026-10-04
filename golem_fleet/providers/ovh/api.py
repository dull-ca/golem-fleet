import hashlib
import json
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from golem_fleet.fault import Fault

ENDPOINTS = {
    "ovh-eu": "https://eu.api.ovh.com/1.0",
    "ovh-ca": "https://ca.api.ovh.com/1.0",
    "ovh-us": "https://api.us.ovhcloud.com/1.0",
}
HTTPS_URL_PREFIX = "https://"
GET_METHOD = "GET"
SIGNATURE_PREFIX = "$1$"
SIGNATURE_SEPARATOR = "+"
SERVER_TIME_PATH = "/auth/time"
NOT_FOUND_STATUS = 404
LOWEST_SUCCESS_STATUS = 200
LOWEST_REDIRECT_STATUS = 300
REQUEST_TIMEOUT_SECONDS = 30.0


class UnknownEndpoint(Fault):
    pass


class MissingCredential(Fault):
    pass


class ResourceNotFound(Fault):
    pass


class RequestFailed(Fault):
    pass


class ResponseNotJson(Fault):
    pass


class ServerTimeNotUnderstood(Fault):
    pass


def base_url_for_endpoint(endpoint: str) -> str:
    known = ENDPOINTS.get(endpoint)
    if known is not None:
        return known
    if endpoint.startswith(HTTPS_URL_PREFIX) and endpoint != HTTPS_URL_PREFIX:
        return endpoint.rstrip("/")
    raise UnknownEndpoint(endpoint)


@dataclass(frozen=True)
class Credentials:
    endpoint: str
    application_key: str
    application_secret: str
    consumer_key: str

    def __post_init__(self) -> None:
        named_values = (
            ("endpoint", self.endpoint),
            ("application key", self.application_key),
            ("application secret", self.application_secret),
            ("consumer key", self.consumer_key),
        )
        for field, value in named_values:
            if not value.strip():
                raise MissingCredential(field)
        base_url_for_endpoint(self.endpoint)

    @property
    def base_url(self) -> str:
        return base_url_for_endpoint(self.endpoint)


class Transport(Protocol):
    def send(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: str | None,
    ) -> tuple[int, str]: ...


@dataclass(frozen=True)
class UrllibTransport:
    timeout_seconds: float = REQUEST_TIMEOUT_SECONDS

    def send(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: str | None,
    ) -> tuple[int, str]:
        request = urllib.request.Request(
            url,
            method=method,
            headers=dict(headers),
            data=None if body is None else body.encode(),
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds
            ) as response:
                return int(response.status), response.read().decode()
        except urllib.error.HTTPError as failure:
            return int(failure.code), failure.read().decode()


def local_time() -> int:
    return int(time.time())


def is_success(status: int) -> bool:
    return LOWEST_SUCCESS_STATUS <= status < LOWEST_REDIRECT_STATUS


def ovh_signature(
    credentials: Credentials,
    method: str,
    url: str,
    body: str,
    timestamp: int,
) -> str:
    payload = SIGNATURE_SEPARATOR.join(
        (
            credentials.application_secret,
            credentials.consumer_key,
            method,
            url,
            body,
            str(timestamp),
        )
    )
    digest = hashlib.sha1(payload.encode(), usedforsecurity=False).hexdigest()
    return f"{SIGNATURE_PREFIX}{digest}"


def decoded_json(path: str, body: str) -> object:
    try:
        return json.loads(body)
    except json.JSONDecodeError as failure:
        raise ResponseNotJson(path, body) from failure


class Client:
    def __init__(self, credentials: Credentials, transport: Transport) -> None:
        self.credentials = credentials
        self.transport = transport
        self.time_drift_seconds: int | None = None

    def url_for(self, path: str) -> str:
        return f"{self.credentials.base_url}/{path.lstrip('/')}"

    def server_time(self) -> int:
        url = self.url_for(SERVER_TIME_PATH)
        status, body = self.transport.send(GET_METHOD, url, {}, None)
        if not is_success(status):
            raise RequestFailed(status, body)
        stripped = body.strip()
        if not stripped.isdigit():
            raise ServerTimeNotUnderstood(body)
        return int(stripped)

    def signed_timestamp(self) -> int:
        if self.time_drift_seconds is None:
            self.time_drift_seconds = self.server_time() - local_time()
        return local_time() + self.time_drift_seconds

    def signed_headers(self, method: str, url: str, body: str) -> dict[str, str]:
        timestamp = self.signed_timestamp()
        return {
            "X-Ovh-Application": self.credentials.application_key,
            "X-Ovh-Consumer": self.credentials.consumer_key,
            "X-Ovh-Timestamp": str(timestamp),
            "X-Ovh-Signature": ovh_signature(
                self.credentials, method, url, body, timestamp
            ),
            "Content-Type": "application/json",
        }

    def get(self, path: str) -> object:
        url = self.url_for(path)
        headers = self.signed_headers(GET_METHOD, url, "")
        status, body = self.transport.send(GET_METHOD, url, headers, None)
        if status == NOT_FOUND_STATUS:
            raise ResourceNotFound(path)
        if not is_success(status):
            raise RequestFailed(status, body)
        return decoded_json(path, body)

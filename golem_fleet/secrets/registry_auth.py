import json

from golem_fleet.fault import Fault


class Unrecognised(Fault):
    pass


def pull_auth(pull_credentials: object, *, registry_host: str) -> str:
    if not isinstance(pull_credentials, str):
        raise Unrecognised(registry_host)
    try:
        document = json.loads(pull_credentials)
    except json.JSONDecodeError as undecodable:
        raise Unrecognised(registry_host) from undecodable
    auths = document.get("auths") if isinstance(document, dict) else None
    entry = auths.get(registry_host) if isinstance(auths, dict) else None
    auth = entry.get("auth") if isinstance(entry, dict) else None
    if not isinstance(auth, str) or not auth:
        raise Unrecognised(registry_host)
    return auth

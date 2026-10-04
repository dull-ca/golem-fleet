import base64

import pytest

from golem_fleet.fleet import machines
from golem_fleet.outputs import cloud_config

AUTH_TOKEN = "golem-auth-token-for-the-fleet"
SECRET_KEY = "golem-secret-key-for-the-fleet"
CREDENTIALS = cloud_config.Credentials(auth_token=AUTH_TOKEN, secret_key=SECRET_KEY)
PROTECTED_CLOUD_CONFIG = f"""#cloud-config
write_files:
  - path: /etc/golem/token
    owner: root:root
    permissions: "0600"
    encoding: b64
    content: {base64.b64encode(AUTH_TOKEN.encode()).decode()}
  - path: /etc/golem/secret-key
    owner: root:root
    permissions: "0600"
    encoding: b64
    content: {base64.b64encode(SECRET_KEY.encode()).decode()}
runcmd:
  - [systemctl, start, golemd.service]
"""


def test_a_protected_machine_carries_no_generation_line() -> None:
    assert cloud_config.render(CREDENTIALS, machines.ProtectedFromReinstall()) == (
        PROTECTED_CLOUD_CONFIG
    )


def test_a_requested_reinstall_carries_the_generation_line_and_no_raw_secret() -> None:
    rendered = cloud_config.render(CREDENTIALS, machines.ReinstallRequested(3))

    assert rendered.splitlines()[:2] == [
        "#cloud-config",
        "# golem-fleet-reinstall-generation: 3",
    ]
    assert AUTH_TOKEN not in rendered
    assert SECRET_KEY not in rendered


def test_an_empty_auth_token_or_an_empty_secret_key_is_refused() -> None:
    with pytest.raises(cloud_config.AuthTokenIsEmpty):
        cloud_config.Credentials(auth_token="", secret_key=SECRET_KEY)

    with pytest.raises(cloud_config.SecretKeyIsEmpty):
        cloud_config.Credentials(auth_token=AUTH_TOKEN, secret_key="   ")

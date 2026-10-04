from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from golem_fleet.addresses import source
from golem_fleet.fleet import placements
from golem_fleet.outputs import files
from golem_fleet.secrets import refresh, secretspec

GOLEMCTL_EXECUTABLE = "golemctl"
FLEET_SUBCOMMAND = "fleet"
INVENTORY_FLAG = "--inventory"
SECRET_PROVIDER_VARIABLE = "SECRETSPEC_PROVIDER"
ENVIRONMENT_SECRET_PROVIDER = "env"
DEFAULT_GENERATED_DIRECTORY = Path("generated")
DEFAULT_MANIFEST_PATH = Path("services") / "main.emet"
DEFAULT_AGENT_BINARY_VARIABLE = "GOLEM_FLEET_GOLEMD"
DEFAULT_OVH_ENDPOINT_VARIABLE = "OVH_ENDPOINT"


@dataclass(frozen=True)
class FleetProgram:
    fleet: placements.Fleet
    addresses: tuple[source.Source, ...]
    artifacts: tuple[files.Artifact, ...] = ()
    generated: Path = DEFAULT_GENERATED_DIRECTORY
    manifest: Path = DEFAULT_MANIFEST_PATH
    secrets: secretspec.SecretsPolicy | None = None
    registry_host: str | None = None
    registry_auth_variable: str | None = None
    pull_credentials_output: str | None = None
    stack: str = "prod"
    passthrough: str | None = None
    program_name: str = "golem-fleet"
    entry_module: str | None = None
    help: str | None = None
    agent_binary_variable: str = DEFAULT_AGENT_BINARY_VARIABLE
    ovh_endpoint_variable: str = DEFAULT_OVH_ENDPOINT_VARIABLE
    secret_entries: Mapping[str, refresh.SecretEntry] = field(default_factory=dict)

    @property
    def inventory(self) -> Path:
        return self.generated / files.INVENTORY_FILENAME

    @property
    def help_text(self) -> str:
        return default_help(self.program_name) if self.help is None else self.help


def default_help(program_name: str) -> str:
    return f"Drive the {program_name} fleet."

import re
from dataclasses import dataclass

from golem_fleet.fault import Fault

SUPPORTED_CHECKSUM_TYPES = ("md5", "sha1", "sha256", "sha512")
BARE_TOML_KEY = re.compile(r"[A-Za-z0-9_-]+")
FIRST_REINSTALL_GENERATION = 0


class ChecksumTypeIsNotSupported(Fault):
    pass


class NameIsNotABareTomlKey(Fault):
    pass


class OvhServiceNameIsEmpty(Fault):
    pass


class ReinstallGenerationIsNegative(Fault):
    pass


@dataclass(frozen=True)
class ImageInstall:
    url: str
    checksum: str
    checksum_type: str
    efi_bootloader_path: str

    def __post_init__(self) -> None:
        if self.checksum_type not in SUPPORTED_CHECKSUM_TYPES:
            raise ChecksumTypeIsNotSupported(
                self.checksum_type, SUPPORTED_CHECKSUM_TYPES
            )


@dataclass(frozen=True)
class ProtectedFromReinstall:
    pass


@dataclass(frozen=True)
class ReinstallRequested:
    generation: int

    def __post_init__(self) -> None:
        if self.generation < FIRST_REINSTALL_GENERATION:
            raise ReinstallGenerationIsNegative(self.generation)


ReinstallPolicy = ProtectedFromReinstall | ReinstallRequested


@dataclass(frozen=True)
class OvhBareMetal:
    service_name: str
    install: ImageInstall
    reinstall: ReinstallPolicy

    def __post_init__(self) -> None:
        if not self.service_name.strip():
            raise OvhServiceNameIsEmpty(self.service_name)


@dataclass(frozen=True)
class Machine:
    name: str
    ovh: OvhBareMetal | None = None

    def __post_init__(self) -> None:
        if not BARE_TOML_KEY.fullmatch(self.name):
            raise NameIsNotABareTomlKey(self.name)

import pytest

from golem_fleet.fleet import machines


def install_checksummed_with(checksum_type: str) -> machines.ImageInstall:
    return machines.ImageInstall(
        url="https://images.example.com/nixos.raw",
        checksum="0" * 64,
        checksum_type=checksum_type,
        efi_bootloader_path=r"\efi\boot\bootx64.efi",
    )


def test_an_ovh_machine_declared_with_an_empty_service_name_is_rejected() -> None:
    with pytest.raises(machines.OvhServiceNameIsEmpty) as refusal:
        machines.OvhBareMetal(
            service_name="   ",
            install=install_checksummed_with("sha256"),
            reinstall=machines.ProtectedFromReinstall(),
        )
    assert refusal.value.args == ("   ",)


def test_the_first_reinstall_generation_is_accepted_but_a_negative_one_is_not() -> None:
    assert machines.ReinstallRequested(0).generation == 0

    with pytest.raises(machines.ReinstallGenerationIsNegative) as refusal:
        machines.ReinstallRequested(-1)
    assert refusal.value.args == (-1,)


def test_unsupported_checksum_type_names_it_and_the_ones_that_work() -> None:
    with pytest.raises(machines.ChecksumTypeIsNotSupported) as refusal:
        install_checksummed_with("crc32")
    assert refusal.value.args == ("crc32", ("md5", "sha1", "sha256", "sha512"))


@pytest.mark.parametrize("name", ["dev-01", "dull_01", "web", "a1"])
def test_bare_toml_key_machine_names_are_accepted(name: str) -> None:
    assert machines.Machine(name).name == name


@pytest.mark.parametrize("name", ["", "dev 01", "dev.01", "dev/01", "dev:01"])
def test_machine_name_that_is_not_a_bare_toml_key_is_rejected(name: str) -> None:
    with pytest.raises(machines.NameIsNotABareTomlKey) as refusal:
        machines.Machine(name)
    assert refusal.value.args == (name,)

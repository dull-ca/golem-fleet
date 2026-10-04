from collections.abc import Callable

import pytest
from fake import RecordingRunner

from golem_fleet.providers.ovh import baremetal

SERVICE_NAME = "ns3141592.ip-51-222-11.net"
PUBLIC_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI golem@fleet"
OVHCLOUD_EXIT_CODE = 2
IPMI_ACCESS_WORDS = f"baremetal ipmi get-access {SERVICE_NAME} --type"
EVERY_BAREMETAL_OPERATION = [
    (baremetal.info, f"baremetal get {SERVICE_NAME} -o json", ()),
    (baremetal.tasks, f"baremetal list-tasks {SERVICE_NAME}", ()),
    (baremetal.interventions, f"baremetal list-interventions {SERVICE_NAME}", ()),
    (baremetal.kvm, f"{IPMI_ACCESS_WORDS} kvmipHtml5URL --ttl 15", ()),
    (baremetal.rescue, f"baremetal reboot-rescue {SERVICE_NAME} --wait", ()),
    (
        baremetal.console,
        f"{IPMI_ACCESS_WORDS} serialOverLanSshKey --ttl 15 --ssh-key",
        (PUBLIC_KEY,),
    ),
]


def ovhcloud_answering(exit_code: int = 0) -> RecordingRunner:
    return RecordingRunner().responds_to_prefix(("ovhcloud",), exit_code=exit_code)


@pytest.mark.parametrize(
    ("operation", "words", "trailing_argv"), EVERY_BAREMETAL_OPERATION
)
def test_a_baremetal_operation_builds_its_argv_and_answers_the_exit_code(
    operation: Callable[..., int],
    words: str,
    trailing_argv: tuple[str, ...],
) -> None:
    runner = ovhcloud_answering(OVHCLOUD_EXIT_CODE)

    exit_code = operation(runner, SERVICE_NAME, *trailing_argv)

    assert tuple(call.argv for call in runner.calls) == (
        ("ovhcloud", *words.split(), *trailing_argv),
    )
    assert exit_code == OVHCLOUD_EXIT_CODE


def test_console_strips_a_key_read_from_a_file_and_refuses_an_empty_one() -> None:
    runner = ovhcloud_answering()

    baremetal.console(runner, SERVICE_NAME, f"{PUBLIC_KEY}\n")

    assert runner.last_call.argv[-1] == PUBLIC_KEY

    with pytest.raises(baremetal.SerialConsoleKeyMissing):
        baremetal.console(runner, SERVICE_NAME, "  \n")

    assert len(runner.calls) == 1

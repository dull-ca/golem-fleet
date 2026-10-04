import pytest
from fake import RecordingRunner

from golem_fleet.addresses import pulumi_stack, source

IPV4 = "203.0.113.7"
IPV6 = "2001:db8::7"
DETAILED = {"ipv4": IPV4, "ipv6": IPV6}
NO_IPV4 = {"ipv6": IPV6}
ODD_IPV6 = {"ipv4": IPV4, "ipv6": 6}
MALFORMED_DOCUMENT = source.AddressDocumentMalformed
MALFORMED_MACHINE = source.MachineAddressMalformed
WITHOUT_IPV4 = source.MachineAddressWithoutIpv4
ONE_DEPLOYED_MACHINE = {"dull-01": source.MachineAddresses(IPV4)}
ONE_MACHINE_DOCUMENT = f'{{"dull-01": "{IPV4}"}}'
LITERAL_MACHINE = "mantis"
LITERAL_IPV4 = "138.197.167.153"
STACK_OUTPUT = "machineAddresses"
STACK_MACHINE = "dev-01"
STACK_IPV4 = "203.0.113.8"
STACK_IPV6 = "2001:db8::8"
STACK_STDOUT = (
    f'{{"{STACK_OUTPUT}": {{"{STACK_MACHINE}": '
    f'{{"ipv4": "{STACK_IPV4}", "ipv6": "{STACK_IPV6}"}}}}}}'
)


def exporting(stdout: str) -> RecordingRunner:
    return RecordingRunner().responds_to_prefix(("pulumi",), stdout=stdout)


def test_machine_addresses_reject_an_empty_ipv4_and_carry_the_paired_ipv6() -> None:
    with pytest.raises(WITHOUT_IPV4) as raised:
        source.MachineAddresses(ipv4="", ipv6=IPV6)

    assert raised.value.args == (IPV6,)


def test_a_machine_is_returned_or_named_as_one_never_deployed() -> None:
    assert source.for_machine(ONE_DEPLOYED_MACHINE, "dull-01").ipv4 == IPV4

    with pytest.raises(source.MachineNeverDeployed) as raised:
        source.for_machine({}, "dull-02")

    assert raised.value.args == ("dull-02",)


def test_one_reader_accepts_a_bare_address_a_detailed_one_and_one_without_ipv6() -> (
    None
):
    read = source.read_every_machine

    assert read({"dev-01": IPV4}) == {"dev-01": source.MachineAddresses(IPV4)}
    assert read({"a": DETAILED}) == {"a": source.MachineAddresses(IPV4, IPV6)}
    assert read({"a": {"ipv4": IPV4}}) == {"a": source.MachineAddresses(IPV4)}


@pytest.mark.parametrize(
    ("document", "rejection", "offending"),
    [
        (["dev-01"], MALFORMED_DOCUMENT, (["dev-01"],)),
        ({7: IPV4}, MALFORMED_DOCUMENT, (7,)),
        ({"a": ""}, WITHOUT_IPV4, (None,)),
        ({"a": 7}, MALFORMED_MACHINE, ("a", 7)),
        ({"a": NO_IPV4}, MALFORMED_MACHINE, ("a", NO_IPV4)),
        ({"a": ODD_IPV6}, MALFORMED_MACHINE, ("a", ODD_IPV6)),
    ],
)
def test_the_reader_rejects_a_document_it_cannot_read(
    document: object,
    rejection: type[Exception],
    offending: tuple[object, ...],
) -> None:
    with pytest.raises(rejection) as raised:
        source.read_every_machine(document)

    assert raised.value.args == offending


def test_a_decoded_address_document_is_an_object_and_nothing_else() -> None:
    assert source.decoded_address_document(ONE_MACHINE_DOCUMENT) == {"dull-01": IPV4}

    for printed in ("not json at all", "[1, 2, 3]"):
        with pytest.raises(MALFORMED_DOCUMENT):
            source.decoded_address_document(printed)


def test_declared_addresses_mix_both_styles_and_never_run_a_command() -> None:
    runner = RecordingRunner()
    declared = source.Declared(
        {
            "dull-01": source.MachineAddresses(ipv4="203.0.113.7", ipv6="2001:db8::7"),
            "dev-01": "203.0.113.8",
        }
    )

    resolved = declared.resolve(runner)

    assert resolved["dull-01"].ipv6 == "2001:db8::7"
    assert resolved["dev-01"].ipv6 is None
    assert runner.calls == ()

    with pytest.raises(source.MachineAddressWithoutIpv4):
        source.Declared({"dev-01": ""})


def test_a_literal_declaration_and_a_stack_output_merge_into_one_fleet() -> None:
    declared = (
        source.Declared({LITERAL_MACHINE: LITERAL_IPV4}),
        pulumi_stack.Output(STACK_OUTPUT),
    )

    assert source.resolve_all(declared, exporting(STACK_STDOUT)) == {
        LITERAL_MACHINE: source.MachineAddresses(LITERAL_IPV4),
        STACK_MACHINE: source.MachineAddresses(STACK_IPV4, STACK_IPV6),
    }


def test_a_machine_two_sources_both_declare_is_named_with_both_addresses() -> None:
    declared = (
        source.Declared({STACK_MACHINE: LITERAL_IPV4}),
        pulumi_stack.Output(STACK_OUTPUT),
    )

    with pytest.raises(source.MachineAddressDeclaredTwice) as raised:
        source.resolve_all(declared, exporting(STACK_STDOUT))

    assert raised.value.args == (
        STACK_MACHINE,
        source.MachineAddresses(LITERAL_IPV4),
        source.MachineAddresses(STACK_IPV4, STACK_IPV6),
    )


def test_no_sources_resolve_to_no_addresses_without_running_a_command() -> None:
    runner = RecordingRunner()

    assert source.resolve_all((), runner) == {}
    assert runner.calls == ()

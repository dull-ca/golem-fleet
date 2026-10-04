from golem_fleet.execution import ports
from golem_fleet.fault import Fault

EXECUTABLE = "ovhcloud"
SUBCOMMAND = "baremetal"
IPMI_COMMAND = "ipmi"
GET_ACCESS_COMMAND = "get-access"
JSON_OUTPUT = ("-o", "json")
ACCESS_TYPE_OPTION = "--type"
ACCESS_TTL_OPTION = "--ttl"
ACCESS_TTL_MINUTES = "15"
SSH_KEY_OPTION = "--ssh-key"
SERIAL_OVER_LAN_ACCESS_TYPE = "serialOverLanSshKey"
KVM_ACCESS_TYPE = "kvmipHtml5URL"
WAIT_OPTION = "--wait"


class SerialConsoleKeyMissing(Fault):
    pass


def info_command(service_name: str) -> list[str]:
    return [EXECUTABLE, SUBCOMMAND, "get", service_name, *JSON_OUTPUT]


def tasks_command(service_name: str) -> list[str]:
    return [EXECUTABLE, SUBCOMMAND, "list-tasks", service_name]


def interventions_command(service_name: str) -> list[str]:
    return [EXECUTABLE, SUBCOMMAND, "list-interventions", service_name]


def ipmi_access_command(service_name: str, access_type: str) -> list[str]:
    return [
        EXECUTABLE,
        SUBCOMMAND,
        IPMI_COMMAND,
        GET_ACCESS_COMMAND,
        service_name,
        ACCESS_TYPE_OPTION,
        access_type,
        ACCESS_TTL_OPTION,
        ACCESS_TTL_MINUTES,
    ]


def console_command(service_name: str, public_key: str) -> list[str]:
    return [
        *ipmi_access_command(service_name, SERIAL_OVER_LAN_ACCESS_TYPE),
        SSH_KEY_OPTION,
        public_key,
    ]


def kvm_command(service_name: str) -> list[str]:
    return ipmi_access_command(service_name, KVM_ACCESS_TYPE)


def rescue_command(service_name: str) -> list[str]:
    return [
        EXECUTABLE,
        SUBCOMMAND,
        "reboot-rescue",
        service_name,
        WAIT_OPTION,
    ]


def info(runner: ports.Runner, service_name: str) -> int:
    return runner.inherit(info_command(service_name))


def tasks(runner: ports.Runner, service_name: str) -> int:
    return runner.inherit(tasks_command(service_name))


def interventions(runner: ports.Runner, service_name: str) -> int:
    return runner.inherit(interventions_command(service_name))


def console(runner: ports.Runner, service_name: str, public_key: str) -> int:
    trimmed_key = public_key.rstrip()
    if not trimmed_key:
        raise SerialConsoleKeyMissing
    return runner.inherit(console_command(service_name, trimmed_key))


def kvm(runner: ports.Runner, service_name: str) -> int:
    return runner.inherit(kvm_command(service_name))


def rescue(runner: ports.Runner, service_name: str) -> int:
    return runner.inherit(rescue_command(service_name))

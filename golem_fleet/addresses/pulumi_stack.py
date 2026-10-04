from dataclasses import dataclass, field

from golem_fleet.addresses import source
from golem_fleet.execution import ports
from golem_fleet.fault import Fault

DEFAULT_STACK = "prod"


class NoSuchOutput(Fault):
    pass


def stack_output_argv(stack: str) -> list[str]:
    return ["pulumi", "stack", "output", "--json", "--show-secrets", "--stack", stack]


def read(runner: ports.Runner, *, stack: str = DEFAULT_STACK) -> dict[str, object]:
    completed = runner.capture(stack_output_argv(stack))
    if not completed.ok:
        raise source.Unavailable(stack, completed.exit_code, completed.stderr.strip())
    return source.decoded_address_document(completed.stdout)


@dataclass(frozen=True)
class Output:
    name: str
    stack: str = field(default=DEFAULT_STACK, kw_only=True)

    def resolve(self, runner: ports.Runner) -> source.Addresses:
        exported = read(runner, stack=self.stack)
        if self.name not in exported:
            raise NoSuchOutput(self.name, self.stack, *sorted(exported))
        return source.read_every_machine(exported[self.name])

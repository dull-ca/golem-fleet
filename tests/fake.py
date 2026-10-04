from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Self, TypedDict, Unpack

from golem_fleet.execution import ports

CAPTURE_METHOD = "capture"
INHERIT_METHOD = "inherit"
INTO_FILE_METHOD = "into_file"


class UnconfiguredCommand(Exception):
    pass


@dataclass(frozen=True)
class RecordedCall:
    method: str
    argv: tuple[str, ...]
    cwd: Path | None = None
    environment: Mapping[str, str] | None = None
    stdin: str | bytes | None = None
    destination: Path | None = None


@dataclass(frozen=True)
class Response:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    raises: Exception | None = None


class Answer(TypedDict, total=False):
    stdout: str
    stderr: str
    exit_code: int
    raises: Exception | None


class CallOptions(TypedDict, total=False):
    cwd: Path | None
    environment: Mapping[str, str] | None
    stdin: str | bytes | None


type ArgvRule = tuple[tuple[str, ...], Answer]


class RecordingRunner:
    def __init__(self) -> None:
        self.recorded: list[RecordedCall] = []
        self.exact_rules: list[ArgvRule] = []
        self.prefix_rules: list[ArgvRule] = []

    def responds_to(self, argv: Sequence[str], **answer: Unpack[Answer]) -> Self:
        self.exact_rules.append((tuple(argv), answer))
        return self

    def responds_to_prefix(
        self, prefix: Sequence[str], **answer: Unpack[Answer]
    ) -> Self:
        self.prefix_rules.append((tuple(prefix), answer))
        return self

    @property
    def calls(self) -> tuple[RecordedCall, ...]:
        return tuple(self.recorded)

    @property
    def last_call(self) -> RecordedCall:
        return self.recorded[-1]

    def calls_to(self, prefix: Sequence[str]) -> tuple[RecordedCall, ...]:
        wanted = tuple(prefix)
        return tuple(call for call in self.calls if call.argv[: len(wanted)] == wanted)

    def capture(
        self, argv: Sequence[str], **options: Unpack[CallOptions]
    ) -> ports.Completed:
        call = RecordedCall(CAPTURE_METHOD, tuple(argv), **options)
        answer = self.answer_for(call)
        return ports.Completed(
            tuple(argv), answer.exit_code, answer.stdout, answer.stderr
        )

    def inherit(self, argv: Sequence[str], **options: Unpack[CallOptions]) -> int:
        call = RecordedCall(INHERIT_METHOD, tuple(argv), **options)
        return self.answer_for(call).exit_code

    def into_file(
        self, argv: Sequence[str], destination: Path, **options: Unpack[CallOptions]
    ) -> int:
        call = RecordedCall(
            INTO_FILE_METHOD, tuple(argv), destination=destination, **options
        )
        answer = self.answer_for(call)
        destination.write_text(answer.stdout, encoding="utf-8")
        return answer.exit_code

    def answer_for(self, call: RecordedCall) -> Response:
        self.recorded.append(call)
        answer = Response(**self.matching_answer(call.argv))
        if answer.raises is not None:
            raise answer.raises
        return answer

    def matching_answer(self, argv: tuple[str, ...]) -> Answer:
        for wanted, answer in reversed(self.exact_rules):
            if argv == wanted:
                return answer
        for prefix, answer in reversed(self.prefix_rules):
            if argv[: len(prefix)] == prefix:
                return answer
        raise UnconfiguredCommand(argv)

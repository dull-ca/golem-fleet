from dataclasses import dataclass, field

import pytest

from golem_fleet.providers.ovh import install_status

SERVICE_NAME = "ns3141592.ip-51-222-11.net"
STATUS_PATH = f"/dedicated/server/{SERVICE_NAME}/install/status"
PARTITIONING = "Partitioning the disks"
INSTALLING = "Installing the distribution"
DEAD_DISK = "disk 2 is dead"
UNNAMED = install_status.InstallStep("(unnamed step)", "", "")


type Followed = tuple[int, tuple[str, ...], tuple[str, ...], tuple[float, ...]]


@dataclass
class ScriptedClient:
    answers: list[object]
    paths: list[str] = field(default_factory=list)

    def get(self, path: str) -> object:
        self.paths.append(path)
        return self.answers.pop(0)


def payload_of(*steps: object) -> dict[str, object]:
    return {"progress": list(steps)}


def step_of(comment: str, status: str) -> dict[str, object]:
    return {"comment": comment, "status": status}


def steps_with(*statuses: str) -> tuple[install_status.InstallStep, ...]:
    return tuple(
        install_status.InstallStep(PARTITIONING, status, "") for status in statuses
    )


def follow(*answers: object) -> Followed:
    client = ScriptedClient(list(answers))
    written: list[str] = []
    slept: list[float] = []
    exit_code = install_status.follow(
        client, SERVICE_NAME, write=written.append, sleep=slept.append
    )
    return exit_code, tuple(client.paths), tuple(written), tuple(slept)


REFUSED_STATUSES = [
    (["done"], ["done"]),
    ({"progress": "done"}, "done"),
    (payload_of("done"), "done"),
]
EVERY_DRAWN_STEP = [
    (
        install_status.InstallStep(PARTITIONING, "todo", ""),
        (f"{install_status.DIM}⬚ {PARTITIONING}{install_status.RESET}",),
    ),
    (
        install_status.InstallStep(PARTITIONING, "hesitating", ""),
        (f"{install_status.DIM}⬚ {PARTITIONING}{install_status.RESET}",),
    ),
    (
        install_status.InstallStep(INSTALLING, "error", DEAD_DISK),
        (
            f"{install_status.RED}❌ {INSTALLING}{install_status.RESET}",
            f"{install_status.RED}    {DEAD_DISK}{install_status.RESET}",
        ),
    ),
]
EVERY_PROGRESS = [
    ((), install_status.Progress.RUNNING),
    (("done", "todo"), install_status.Progress.RUNNING),
    (("done", "done"), install_status.Progress.DONE),
    (("done", "error"), install_status.Progress.ERROR),
]


@pytest.mark.parametrize("payload", [{}, {"progress": None}, payload_of()])
def test_parse_reads_no_step_from_an_install_without_progress(payload: object) -> None:
    assert install_status.parse(payload) == ()


@pytest.mark.parametrize("step", [{}, {"comment": None, "status": None, "error": None}])
def test_parse_names_a_step_whose_fields_are_missing_or_null(step: object) -> None:
    assert install_status.parse(payload_of(step)) == (UNNAMED,)


def test_parse_reads_the_comment_status_and_error_of_each_step() -> None:
    payload = payload_of(
        step_of(PARTITIONING, "done"),
        {"comment": INSTALLING, "status": "error", "error": DEAD_DISK},
    )

    assert install_status.parse(payload) == (
        install_status.InstallStep(PARTITIONING, "done", ""),
        install_status.InstallStep(INSTALLING, "error", DEAD_DISK),
    )


@pytest.mark.parametrize(("payload", "refused"), REFUSED_STATUSES)
def test_parse_refuses_a_status_that_is_not_an_object_of_step_objects(
    payload: object, refused: object
) -> None:
    with pytest.raises(install_status.NotUnderstood) as raised:
        install_status.parse(payload)

    assert raised.value.args == (refused,)


@pytest.mark.parametrize(("step", "expected"), EVERY_DRAWN_STEP)
def test_a_step_is_drawn_with_the_colour_icon_and_detail_of_its_status(
    step: install_status.InstallStep, expected: tuple[str, ...]
) -> None:
    assert install_status.status_lines((step,)) == expected


@pytest.mark.parametrize(("statuses", "expected"), EVERY_PROGRESS)
def test_progress_follows_the_statuses_of_every_step(
    statuses: tuple[str, ...], expected: install_status.Progress
) -> None:
    assert install_status.progress_of(steps_with(*statuses)) is expected


def test_follow_rewinds_over_what_it_drew_until_every_step_is_done() -> None:
    exit_code, paths, written, slept = follow(
        payload_of(step_of(PARTITIONING, "doing")),
        payload_of(step_of(PARTITIONING, "done")),
    )

    assert exit_code == 0
    assert paths == (STATUS_PATH, STATUS_PATH)
    assert slept == (install_status.POLL_SECONDS,)
    assert written == (
        f"\x1b[2K{install_status.YELLOW}⏳ {PARTITIONING}{install_status.RESET}\n",
        "\x1b[1A",
        f"\x1b[2K{install_status.GREEN}✅ {PARTITIONING}{install_status.RESET}\n",
    )


def test_follow_stops_with_a_failure_when_a_step_errors() -> None:
    exit_code, _, _, slept = follow(
        payload_of(step_of(PARTITIONING, "doing")),
        payload_of(step_of("boot", "error")),
    )

    assert exit_code == 1
    assert slept == (install_status.POLL_SECONDS,)

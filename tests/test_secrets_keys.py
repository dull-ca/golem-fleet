import signal
import stat
from pathlib import Path

import pytest

from golem_fleet.secrets import keys

WELL_FORMED_KEY = "ab" * 64
RUNTIME_DIRECTORY_VARIABLE = "XDG_RUNTIME_DIR"


class DeliberateFailure(Exception):
    pass


def test_a_well_formed_key_is_kept_verbatim() -> None:
    assert keys.FleetKey(WELL_FORMED_KEY).value == WELL_FORMED_KEY


@pytest.mark.parametrize("wrong_length", ["ab" * 63, "ab" * 65, ""])
def test_a_key_of_the_wrong_length_carries_the_length_supplied_and_required(
    wrong_length: str,
) -> None:
    with pytest.raises(keys.WrongLength) as raised:
        keys.FleetKey(wrong_length)

    assert raised.value.args == (len(wrong_length), keys.LENGTH)


@pytest.mark.parametrize("outside_the_alphabet", ["AB" * 64, "zz" * 64])
def test_a_key_outside_the_alphabet_is_never_reported_as_a_length(
    outside_the_alphabet: str,
) -> None:
    with pytest.raises(keys.NotLowercaseHexadecimal) as raised:
        keys.FleetKey(outside_the_alphabet)

    assert raised.value.args == ()
    assert str(keys.LENGTH) not in repr(raised.value)
    assert outside_the_alphabet not in repr(raised.value)


def test_the_key_root_falls_back_to_shared_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(RUNTIME_DIRECTORY_VARIABLE, raising=False)

    assert keys.secret_key_root() == Path("/dev") / "shm"


def test_the_key_file_lives_under_the_chosen_root_at_mode_600_then_goes_away(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(RUNTIME_DIRECTORY_VARIABLE, str(tmp_path))
    before = (signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM))

    with keys.materialised(keys.FleetKey(WELL_FORMED_KEY)) as key_path:
        directory = key_path.parent
        assert key_path.name == "secret-key"
        assert directory.parent == tmp_path
        assert directory.name.startswith("golem-fleet-key-")
        assert key_path.read_text(encoding="utf-8") == WELL_FORMED_KEY
        assert stat.S_IMODE(key_path.stat().st_mode) == 0o600
        assert signal.getsignal(signal.SIGINT) is not before[0]

    assert not directory.exists()
    assert list(tmp_path.iterdir()) == []
    assert (signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)) == before


def fail_while_materialised(seen: list[Path]) -> None:
    with keys.materialised(keys.FleetKey(WELL_FORMED_KEY)) as key_path:
        seen.append(key_path)
        raise DeliberateFailure


def test_the_whole_directory_is_removed_when_the_body_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(RUNTIME_DIRECTORY_VARIABLE, str(tmp_path))
    seen: list[Path] = []

    with pytest.raises(DeliberateFailure):
        fail_while_materialised(seen)

    assert not seen[0].parent.exists()


def signal_while_materialised(number: signal.Signals, seen: list[Path]) -> None:
    with keys.materialised(keys.FleetKey(WELL_FORMED_KEY)) as key_path:
        seen.append(key_path)
        handler = signal.getsignal(number)
        assert handler is not None
        assert not isinstance(handler, int)
        handler(int(number), None)


def test_a_signal_removes_the_directory_and_exits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(RUNTIME_DIRECTORY_VARIABLE, str(tmp_path))

    for number, expected_exit_code in ((signal.SIGINT, 130), (signal.SIGTERM, 143)):
        seen: list[Path] = []

        with pytest.raises(SystemExit) as raised:
            signal_while_materialised(number, seen)

        assert raised.value.code == expected_exit_code
        assert not seen[0].parent.exists()
        assert list(tmp_path.iterdir()) == []

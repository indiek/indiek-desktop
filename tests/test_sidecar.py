"""DESKTOP:PACKAGING-TAURI P3: the `indiek-sidecar` entry point dispatches serve / ik."""

from __future__ import annotations

import sys

import pytest

import indiek_sidecar


@pytest.mark.parametrize("argv", [[], ["help"], ["--handshake"]])
def test_unknown_commands_print_usage(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    assert indiek_sidecar.main(argv) == 2
    assert "usage: indiek-sidecar" in capsys.readouterr().err


def test_serve_runs_the_api_with_the_remaining_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr("indiek_api.app.main", lambda argv: calls.append(list(argv)))
    assert indiek_sidecar.main(["serve", "--handshake", "--exit-on-stdin-eof"]) == 0
    assert calls == [["--handshake", "--exit-on-stdin-eof"]]


def test_ik_runs_the_cli_with_its_own_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []
    monkeypatch.setattr("indiek.cli.main", lambda: seen.append(list(sys.argv)))
    monkeypatch.setattr(sys, "argv", ["indiek-sidecar"])
    assert indiek_sidecar.main(["ik", "key", "status"]) == 0
    assert seen == [["ik", "key", "status"]]


def test_ik_exit_codes_propagate(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail() -> None:
        raise SystemExit(3)

    monkeypatch.setattr("indiek.cli.main", fail)
    with pytest.raises(SystemExit) as exit_info:
        indiek_sidecar.main(["ik", "nope"])
    assert exit_info.value.code == 3

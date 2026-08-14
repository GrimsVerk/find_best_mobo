"""Project-wide test guards.

The suite must run offline and deterministically (AGENTS.md): this autouse
fixture makes any socket connection attempt fail the test that made it.
Tests that legitimately need a network boundary mock it instead.
"""

import socket
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    def guard(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Tests must not touch the network (see AGENTS.md).")

    monkeypatch.setattr(socket.socket, "connect", guard)
    yield

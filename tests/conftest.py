"""Tests run offline: any non-loopback socket connection fails the test.

Opt one test out with @pytest.mark.allow_network.
"""

import socket
from collections.abc import Iterator

import pytest

_LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost"})


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "allow_network: permit real outbound connections in this test "
        "(exempts it from the offline guarantee in AGENTS.md)",
    )


def _is_loopback(address: object) -> bool:
    # AF_UNIX addresses are plain strings (a filesystem path) and never leave
    # the machine; AF_INET/AF_INET6 are (host, port, ...) tuples.
    if isinstance(address, str):
        return True
    if isinstance(address, tuple) and address:
        return str(address[0]) in _LOOPBACK
    return False


@pytest.fixture(autouse=True)
def no_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    if request.node.get_closest_marker("allow_network"):
        yield
        return

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def guard(self: socket.socket, address: object) -> object:
        if _is_loopback(address):
            return real_connect(self, address)  # type: ignore[arg-type]
        raise RuntimeError(
            f"Tests must not touch the network (see AGENTS.md): {address!r}. "
            "Mock the boundary, or mark the test @pytest.mark.allow_network "
            "if it genuinely must reach out."
        )

    def guard_ex(self: socket.socket, address: object) -> object:
        if _is_loopback(address):
            return real_connect_ex(self, address)  # type: ignore[arg-type]
        raise RuntimeError(f"Tests must not touch the network (see AGENTS.md): {address!r}.")

    # connect_ex too: it is the same call with an errno return instead of an
    # exception, and patching only `connect` left an open door.
    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(socket.socket, "connect_ex", guard_ex)
    yield

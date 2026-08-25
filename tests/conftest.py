"""Project-wide test guards.

The suite must run offline and deterministically (AGENTS.md): this autouse
fixture makes any outbound socket connection fail the test that made it.
Tests that legitimately need a network boundary mock it instead.

Two deliberate carve-outs, because the blunt version of this rule blocks things
that are not "the network" in any sense that matters:

- **Loopback is allowed.** A test that starts a local server, or uses anything
  built on a local socket pair, is not reaching the outside world and is still
  perfectly deterministic. Blocking it forbids a whole category of honest tests
  and teaches people to disable the fixture wholesale.
- **`@pytest.mark.allow_network`** opts a single test out entirely, for the rare
  case that has to be tested against something real. It is deliberately noisy:
  it names itself in the test, so it shows up in review rather than hiding in a
  conftest edit. A test wearing this marker is not part of the offline
  guarantee, and CI may well be the place it fails.
"""

import socket
from collections.abc import Iterator

import pytest

from find_best_mobo import calibration

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


@pytest.fixture(autouse=True)
def isolated_calibration_records(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No test may see the calibration records of the machine it runs on.

    `calibration.RECORD_DIR` is a RELATIVE path, so it resolves against the
    working directory, and the working directory during a normal `pytest` run is
    the repository root — where the committed records live. `estimate` prefers a
    measured chars-per-token factor over the configured guess whenever a record
    is there, so ten tests that assert on the configured factor passed for weeks
    and then failed the moment the first real calibration batch was run and
    committed. Nothing about those tests was wrong; the suite was reading the
    developer's data directory.

    Pointing the constant at an empty per-test directory restores the property
    the suite is supposed to have: the same result on a clean checkout, on this
    machine, and in CI, whether or not anyone has ever spent money here.

    ONE MODULE IS EXEMPT. `tests/test_calibration.py` asserts on where the
    record lives in the real repository — that it is under `calibration/`, that
    it is not under the gitignored `data/`, that `.gitignore` does not swallow
    it, and that `acceptance/S3.sh` arrives with the first real record. Those
    are claims about this checkout, not about a temporary directory, and
    redirecting the constant would make every one of them assert on a tmpdir and
    pass regardless. The exemption is by module rather than by marker so that
    the blind-written tests are not edited to accommodate a fixture; tests in
    that module which want an empty directory patch the constant themselves,
    and a later `monkeypatch.setattr` wins over this one either way.
    """
    if request.path.name == "test_calibration.py":
        return
    monkeypatch.setattr(calibration, "RECORD_DIR", tmp_path_factory.mktemp("calibration-records"))

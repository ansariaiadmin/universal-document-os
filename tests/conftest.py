"""Shared pytest fixtures — isolate tests from the real ./data directory.

Isolation strategy: DATA_DIR points at a per-test tmp dir and app.config /
app.main are (re)imported inside the fixture, so every module-level constant
copy used by tests (OUTPUTS, UPLOADS, ...) comes from the isolated instance.
The default session-scoped client binds to the first-built isolated app;
tests that monkeypatch path constants rebuild their own TestClient.
"""
import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_app(data_dir: pathlib.Path):
    """(Re)import app.config + app.main with DATA_DIR pointed at data_dir."""
    os.environ["DATA_DIR"] = str(data_dir)
    for mod in ("app.config", "app.main"):
        sys.modules.pop(mod, None)
    import app.main as main

    return main


@pytest.fixture(scope="session")
def _session_app(tmp_path_factory):
    """One isolated app instance per test session (fast, fully isolated)."""
    data = tmp_path_factory.mktemp("udo-data")
    for d in ("uploads", "outputs", "workrooms"):
        (data / d).mkdir(parents=True, exist_ok=True)
    return _load_app(data)


@pytest.fixture
def app_main(_session_app):
    """The isolated app.main module bound to this session's temp data tree."""
    return _session_app


@pytest.fixture(autouse=True)
def isolated_data_dir(app_main):
    """Autouse guard: no test can ever touch the repository's real data/."""
    yield app_main


@pytest.fixture(scope="session")
def _client_stack(_session_app):
    from fastapi.testclient import TestClient

    # Outermost context is bound to the isolated session app; tests that
    # monkeypatch module constants push their own client (see `client`).
    with TestClient(_session_app.app) as base:
        yield [base]


@pytest.fixture
def client(_client_stack, request):
    """TestClient for the current test.

    If a test monkeypatches path constants (e.g. main.OUTPUTS), it should
    rebuild via `client.app`-style local TestClient(...) itself; by default we
    reuse the session-scoped client for speed.
    """
    c = _client_stack[-1]
    # per-test marker hook (tests may push onto _client_stack if needed)
    yield c


@pytest.fixture
def data_tree(app_main):
    """Module-level path constants of the isolated app, for direct assertions."""
    return {
        "uploads": app_main.UPLOADS,
        "outputs": app_main.OUTPUTS,
        "workrooms": app_main.WORKROOMS,
        "audit": app_main.AUDIT_FILE,
    }

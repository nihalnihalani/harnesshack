"""Shared fixtures — in-process testing of real code via FastAPI TestClient.

External services are NOT mocked. Tests control the ENVIRONMENT (the real
configuration surface): credential env vars are removed so every test runs
in the honest unconfigured state that exists while BUILD-STATE.md blockers
B1-B9 are open.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api import main as api_main

ALL_CREDENTIAL_ENV_VARS = [
    var for env_vars in api_main.DEPENDENCY_ENV_VARS.values() for var in env_vars
]


@pytest.fixture(autouse=True)
def unconfigured_env(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Guarantee the unconfigured state and reset per-process API state.

    Live-marked tests (`pytest -m live`) are the one exception: they exist to
    exercise REAL services, so they keep whatever credentials the environment
    provides instead of having them stripped.
    """
    if request.node.get_closest_marker("live"):
        yield
        return
    for var in ALL_CREDENTIAL_ENV_VARS + ["WEBHOOK_AUTH_TOKEN", "RATE_LIMIT_PER_MINUTE"]:
        monkeypatch.delenv(var, raising=False)
    api_main._seen_keys.clear()
    api_main._agents.clear()
    api_main._rate_limiter.reset()
    yield
    api_main._seen_keys.clear()
    api_main._agents.clear()
    api_main._rate_limiter.reset()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(api_main.app)

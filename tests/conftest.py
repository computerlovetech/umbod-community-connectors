import httpx
import pytest


@pytest.fixture(autouse=True)
def no_live_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("Live HTTP is forbidden in tests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", denied)

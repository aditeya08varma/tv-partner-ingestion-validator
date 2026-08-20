import httpx
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport

from app.main import app


@pytest.fixture()
def client():
    """A TestClient whose internal http_client is rewired to talk to the same
    in-process ASGI app, so manifest fetch/segment-probe logic can be
    exercised end-to-end without a real network or a live server."""
    with TestClient(app) as c:
        app.state.http_client = httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        )
        yield c

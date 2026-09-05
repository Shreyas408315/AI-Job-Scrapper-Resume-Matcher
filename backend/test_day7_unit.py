from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.deps import _rate_limit_buckets, rate_limit
from app.main import app


def request_for(path: str = "/api/test"):
    return SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        scope={"path": path},
    )


def test_rate_limiter_returns_429_after_limit():
    _rate_limit_buckets.clear()
    dependency = rate_limit(2, 60)

    dependency(request_for())
    dependency(request_for())

    with pytest.raises(HTTPException) as error:
        dependency(request_for())

    assert error.value.status_code == 429
    assert error.value.headers["Retry-After"]
    _rate_limit_buckets.clear()


def test_rate_limiter_separates_routes_and_clients():
    _rate_limit_buckets.clear()
    dependency = rate_limit(1, 60)
    first = request_for("/api/jobs/sync/acme")
    other_route = request_for("/api/matches/123")
    other_route.client.host = "127.0.0.2"

    dependency(first)
    dependency(other_route)
    with pytest.raises(HTTPException):
        dependency(first)

    _rate_limit_buckets.clear()


def test_security_headers_are_present_on_public_health_check():
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"

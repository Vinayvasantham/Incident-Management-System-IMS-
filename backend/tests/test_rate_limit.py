from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app, limiter


def test_ingest_rate_limit_returns_429(monkeypatch):
    client = TestClient(app)

    async def deny() -> bool:
        return False

    monkeypatch.setattr(limiter, "allow", deny)

    response = client.post(
        "/ingest",
        json={"component_id": "CACHE_01", "component_type": "CACHE", "message": "spike"},
    )

    assert response.status_code == 429
    assert response.json()["detail"] == "Rate limit exceeded"

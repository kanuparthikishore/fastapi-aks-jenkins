from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_returns_200():
    r = client.get("/health")
    assert r.status_code == 200


def test_health_status_field():
    r = client.get("/health")
    assert r.json()["status"] == "healthy"


def test_health_version_field():
    r = client.get("/health")
    assert "version" in r.json()

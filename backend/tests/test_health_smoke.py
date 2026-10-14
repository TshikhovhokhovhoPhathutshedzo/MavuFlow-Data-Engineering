import os

os.environ["DATABASE_URL"] = "sqlite:///./test_health_smoke.db"

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_backend_health_endpoints() -> None:
    root_response = client.get("/health")
    assert root_response.status_code == 200, root_response.text
    payload = root_response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "MavuFlow Studio"
    assert payload["environment"] in {"development", "production", "test"}
    assert payload["version"]

    api_response = client.get("/api/v1/health")
    assert api_response.status_code == 200, api_response.text
    api_payload = api_response.json()
    assert api_payload["status"] == "ok"
    assert api_payload["api"] == "MavuFlow Studio"
    assert api_payload["environment"] in {"development", "production", "test"}
    assert api_payload["version"]

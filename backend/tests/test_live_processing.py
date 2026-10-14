import os
import uuid

os.environ["DATABASE_URL"] = "sqlite:///./test_live_processing.db"

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def register_user(email: str, password: str = "StrongPass123!") -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Live Processing User",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def test_live_processing_creates_versioned_dataset() -> None:
    email = f"liveproc_{uuid.uuid4().hex[:8]}@example.com"
    token = register_user(email)
    headers = {"Authorization": f"Bearer {token}"}

    project_response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Live Processing", "description": "Versioned analysis"},
    )
    assert project_response.status_code == 201, project_response.text
    project_id = project_response.json()["id"]

    dataset_response = client.post(
        "/api/v1/datasets/upload",
        headers=headers,
        data={"project_id": project_id, "name": "orders.csv"},
        files={"file": ("orders.csv", b"customer,amount\nAlice,120\nBob,50\nCharlie,90\n", "text/csv")},
    )
    assert dataset_response.status_code == 201, dataset_response.text
    dataset_id = dataset_response.json()["id"]

    process_response = client.post(
        f"/api/v1/datasets/{dataset_id}/process",
        headers=headers,
        json={"operation": "rename_columns", "mapping": {"customer": "customer_name"}},
    )
    assert process_response.status_code == 200, process_response.text
    process_payload = process_response.json()
    assert process_payload["status"] == "processed"
    assert process_payload["version_number"] == 2
    assert process_payload["preview"][0]["customer_name"] == "Alice"

    versions_response = client.get(f"/api/v1/datasets/{dataset_id}/versions", headers=headers)
    assert versions_response.status_code == 200, versions_response.text
    versions = versions_response.json()
    assert len(versions) >= 2
    assert versions[0]["version_number"] >= 1


def test_live_processing_requires_ownership() -> None:
    owner_email = f"owner_live_{uuid.uuid4().hex[:8]}@example.com"
    viewer_email = f"viewer_live_{uuid.uuid4().hex[:8]}@example.com"
    owner_token = register_user(owner_email)
    viewer_token = register_user(viewer_email)

    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    project_response = client.post(
        "/api/v1/projects",
        headers=owner_headers,
        json={"name": "Restricted Processing", "description": "Owner only"},
    )
    project_id = project_response.json()["id"]

    dataset_response = client.post(
        "/api/v1/datasets/upload",
        headers=owner_headers,
        data={"project_id": project_id, "name": "process_me.csv"},
        files={"file": ("process_me.csv", b"customer,amount\nAlice,10\nBob,20\n", "text/csv")},
    )
    dataset_id = dataset_response.json()["id"]

    response = client.post(
        f"/api/v1/datasets/{dataset_id}/process",
        headers=viewer_headers,
        json={"operation": "rename_columns", "mapping": {"customer": "customer_name"}},
    )
    assert response.status_code == 403

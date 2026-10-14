import os
import uuid

os.environ["DATABASE_URL"] = "sqlite:///./test_export_system.db"

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def register_user(email: str, password: str = "StrongPass123!") -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Export User",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def test_dataset_export_downloads_csv() -> None:
    email = f"export_csv_{uuid.uuid4().hex[:8]}@example.com"
    token = register_user(email)
    headers = {"Authorization": f"Bearer {token}"}

    project_response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Export Project", "description": "Download tests"},
    )
    assert project_response.status_code == 201, project_response.text
    project_id = project_response.json()["id"]

    dataset_response = client.post(
        "/api/v1/datasets/upload",
        headers=headers,
        data={"project_id": project_id, "name": "export_me.csv"},
        files={"file": ("export_me.csv", b"customer,amount\nAlice,120\nBob,50\n", "text/csv")},
    )
    assert dataset_response.status_code == 201, dataset_response.text
    dataset_id = dataset_response.json()["id"]

    response = client.get(f"/api/v1/datasets/{dataset_id}/export", headers=headers, params={"format": "csv"})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert "customer,amount" in response.text
    assert "Alice" in response.text


def test_dataset_export_requires_ownership() -> None:
    owner_email = f"export_owner_{uuid.uuid4().hex[:8]}@example.com"
    viewer_email = f"export_viewer_{uuid.uuid4().hex[:8]}@example.com"
    owner_token = register_user(owner_email)
    viewer_token = register_user(viewer_email)

    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    project_response = client.post(
        "/api/v1/projects",
        headers=owner_headers,
        json={"name": "Restricted Export", "description": "Owner only"},
    )
    project_id = project_response.json()["id"]

    dataset_response = client.post(
        "/api/v1/datasets/upload",
        headers=owner_headers,
        data={"project_id": project_id, "name": "restricted.csv"},
        files={"file": ("restricted.csv", b"customer,amount\nAlice,10\n", "text/csv")},
    )
    dataset_id = dataset_response.json()["id"]

    response = client.get(f"/api/v1/datasets/{dataset_id}/export", headers=viewer_headers, params={"format": "json"})
    assert response.status_code == 403

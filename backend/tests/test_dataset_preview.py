import os
import uuid

os.environ["DATABASE_URL"] = "sqlite:///./test_dataset_preview.db"

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def register_user(email: str, password: str = "StrongPass123!") -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Preview User",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def test_dataset_preview_and_profile_endpoints() -> None:
    email = f"preview_{uuid.uuid4().hex[:8]}@example.com"
    token = register_user(email)
    headers = {"Authorization": f"Bearer {token}"}

    project_response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Preview Project", "description": "Quality checks"},
    )
    assert project_response.status_code == 201, project_response.text
    project_id = project_response.json()["id"]

    dataset_response = client.post(
        "/api/v1/datasets/upload",
        headers=headers,
        data={"project_id": project_id, "name": "customers.csv"},
        files={"file": ("customers.csv", b"customer,amount,segment\nAlice,120,retail\nBob,,retail\nAlice,120,retail\nCharlie,90,enterprise\n", "text/csv")},
    )
    assert dataset_response.status_code == 201, dataset_response.text
    dataset_id = dataset_response.json()["id"]

    preview_response = client.get(f"/api/v1/datasets/{dataset_id}/preview?limit=2", headers=headers)
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    assert len(preview["rows"]) == 2
    assert preview["total_rows"] == 4
    assert preview["columns"] == ["customer", "amount", "segment"]

    profile_response = client.get(f"/api/v1/datasets/{dataset_id}/profile", headers=headers)
    assert profile_response.status_code == 200, profile_response.text
    profile = profile_response.json()
    assert profile["row_count"] == 4
    assert profile["column_count"] == 3
    assert profile["duplicate_rows"] == 1
    assert profile["missing_values_total"] == 1
    assert any(item["name"] == "amount" and item["null_count"] == 1 for item in profile["columns"])


def test_dataset_preview_requires_ownership() -> None:
    owner_email = f"owner_preview_{uuid.uuid4().hex[:8]}@example.com"
    viewer_email = f"viewer_preview_{uuid.uuid4().hex[:8]}@example.com"
    owner_token = register_user(owner_email)
    viewer_token = register_user(viewer_email)

    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    project_response = client.post(
        "/api/v1/projects",
        headers=owner_headers,
        json={"name": "Restricted Preview", "description": "Owner only"},
    )
    project_id = project_response.json()["id"]

    dataset_response = client.post(
        "/api/v1/datasets/upload",
        headers=owner_headers,
        data={"project_id": project_id, "name": "preview_data.csv"},
        files={"file": ("preview_data.csv", b"id,value\n1,10\n2,20\n", "text/csv")},
    )
    dataset_id = dataset_response.json()["id"]

    response = client.get(f"/api/v1/datasets/{dataset_id}/profile", headers=viewer_headers)
    assert response.status_code == 403

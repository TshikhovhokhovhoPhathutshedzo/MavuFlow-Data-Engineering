import os
import uuid

os.environ["DATABASE_URL"] = "sqlite:///./test_cleaning_engine.db"

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def register_user(email: str, password: str = "StrongPass123!") -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Cleaner User",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def test_cleaning_engine_applies_rules_and_updates_dataset() -> None:
    email = f"cleaner_{uuid.uuid4().hex[:8]}@example.com"
    token = register_user(email)
    headers = {"Authorization": f"Bearer {token}"}

    project_response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Cleaning Project", "description": "Quality cleanup"},
    )
    assert project_response.status_code == 201, project_response.text
    project_id = project_response.json()["id"]

    dataset_response = client.post(
        "/api/v1/datasets/upload",
        headers=headers,
        data={"project_id": project_id, "name": "customers.csv"},
        files={"file": ("customers.csv", b"customer,amount,segment\n Alice ,120,retail\nBob,,retail\nCharlie,90,enterprise\n", "text/csv")},
    )
    assert dataset_response.status_code == 201, dataset_response.text
    dataset_id = dataset_response.json()["id"]

    clean_response = client.post(
        f"/api/v1/datasets/{dataset_id}/clean",
        headers=headers,
        json={
            "operations": [
                {"type": "trim_whitespace", "column": "customer"},
                {"type": "fill_missing", "column": "amount", "value": 0},
            ]
        },
    )

    assert clean_response.status_code == 200, clean_response.text
    body = clean_response.json()
    assert body["row_count"] == 3
    assert body["column_count"] == 3
    assert body["preview"][0]["customer"] == "Alice"
    assert body["preview"][1]["amount"] == 0


def test_cleaning_engine_requires_ownership() -> None:
    owner_email = f"owner_clean_{uuid.uuid4().hex[:8]}@example.com"
    viewer_email = f"viewer_clean_{uuid.uuid4().hex[:8]}@example.com"
    owner_token = register_user(owner_email)
    viewer_token = register_user(viewer_email)

    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    project_response = client.post(
        "/api/v1/projects",
        headers=owner_headers,
        json={"name": "Owner Only Cleaning", "description": "Restricted"},
    )
    project_id = project_response.json()["id"]

    dataset_response = client.post(
        "/api/v1/datasets/upload",
        headers=owner_headers,
        data={"project_id": project_id, "name": "clean_me.csv"},
        files={"file": ("clean_me.csv", b"customer,amount\nAlice,10\nBob,20\n", "text/csv")},
    )
    dataset_id = dataset_response.json()["id"]

    response = client.post(
        f"/api/v1/datasets/{dataset_id}/clean",
        headers=viewer_headers,
        json={"operations": [{"type": "trim_whitespace", "column": "customer"}]},
    )
    assert response.status_code == 403

import os
import uuid

os.environ["DATABASE_URL"] = "sqlite:///./test_analytics_quality.db"

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def register_user(email: str, password: str = "StrongPass123!") -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Analytics User",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def test_dataset_analytics_and_quality_report() -> None:
    email = f"analytics_{uuid.uuid4().hex[:8]}@example.com"
    token = register_user(email)
    headers = {"Authorization": f"Bearer {token}"}

    project_response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Analytics Project", "description": "Metrics and quality"},
    )
    assert project_response.status_code == 201, project_response.text
    project_id = project_response.json()["id"]

    dataset_response = client.post(
        "/api/v1/datasets/upload",
        headers=headers,
        data={"project_id": project_id, "name": "analytics.csv"},
        files={
            "file": (
                "analytics.csv",
                b"customer,amount,city\nAlice,120,NY\nBob,,LA\nCharlie,200,NY\nAlice,120,NY\n",
                "text/csv",
            )
        },
    )
    assert dataset_response.status_code == 201, dataset_response.text
    dataset_id = dataset_response.json()["id"]

    analytics_response = client.get(f"/api/v1/datasets/{dataset_id}/analytics", headers=headers)
    assert analytics_response.status_code == 200, analytics_response.text
    analytics = analytics_response.json()
    assert analytics["row_count"] == 4
    assert analytics["column_count"] == 3
    assert 0 <= analytics["quality_score"] <= 100
    assert analytics["missing_values_total"] >= 1
    assert analytics["duplicate_rows"] >= 1

    report_response = client.get(f"/api/v1/datasets/{dataset_id}/quality-report", headers=headers)
    assert report_response.status_code == 200, report_response.text
    report = report_response.json()
    assert report["dataset_id"] == dataset_id
    assert 0 <= report["quality_score"] <= 100
    assert report["summary"]["status"] in {"excellent", "good", "fair", "poor"}


def test_dataset_analytics_requires_ownership() -> None:
    owner_email = f"analytics_owner_{uuid.uuid4().hex[:8]}@example.com"
    viewer_email = f"analytics_viewer_{uuid.uuid4().hex[:8]}@example.com"
    owner_token = register_user(owner_email)
    viewer_token = register_user(viewer_email)

    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    project_response = client.post(
        "/api/v1/projects",
        headers=owner_headers,
        json={"name": "Restricted Analytics", "description": "Owner only"},
    )
    project_id = project_response.json()["id"]

    dataset_response = client.post(
        "/api/v1/datasets/upload",
        headers=owner_headers,
        data={"project_id": project_id, "name": "private.csv"},
        files={"file": ("private.csv", b"customer,amount\nAlice,10\n", "text/csv")},
    )
    dataset_id = dataset_response.json()["id"]

    analytics_response = client.get(f"/api/v1/datasets/{dataset_id}/analytics", headers=viewer_headers)
    assert analytics_response.status_code == 403

    report_response = client.get(f"/api/v1/datasets/{dataset_id}/quality-report", headers=viewer_headers)
    assert report_response.status_code == 403

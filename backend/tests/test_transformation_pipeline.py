import os
import uuid

os.environ["DATABASE_URL"] = "sqlite:///./test_transformation_pipeline.db"

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def register_user(email: str, password: str = "StrongPass123!") -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Pipeline User",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def test_transformation_engine_and_pipeline_builder() -> None:
    email = f"transform_{uuid.uuid4().hex[:8]}@example.com"
    token = register_user(email)
    headers = {"Authorization": f"Bearer {token}"}

    project_response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Transformation Project", "description": "Revenue pipeline"},
    )
    assert project_response.status_code == 201, project_response.text
    project_id = project_response.json()["id"]

    dataset_response = client.post(
        "/api/v1/datasets/upload",
        headers=headers,
        data={"project_id": project_id, "name": "revenue.csv"},
        files={"file": ("revenue.csv", b"customer,amount\nAlice,120\nBob,80\n", "text/csv")},
    )
    assert dataset_response.status_code == 201, dataset_response.text
    dataset_id = dataset_response.json()["id"]

    transform_response = client.post(
        f"/api/v1/datasets/{dataset_id}/transform",
        headers=headers,
        json={
            "operations": [
                {"type": "rename_columns", "mapping": {"customer": "customer_name"}},
                {"type": "compute_column", "column": "profit", "expression": "amount * 0.5"},
            ]
        },
    )
    assert transform_response.status_code == 200, transform_response.text
    transform_payload = transform_response.json()
    assert transform_payload["status"] == "transformed"
    assert transform_payload["preview"][0]["customer_name"] == "Alice"
    assert transform_payload["preview"][0]["profit"] == 60.0

    pipeline_response = client.post(
        "/api/v1/pipelines",
        headers=headers,
        json={
            "name": "Revenue Flow",
            "description": "Normalize and enrich revenue",
            "dataset_id": dataset_id,
            "steps": [
                {"operation": "rename_columns", "config": {"mapping": {"customer": "customer_name"}}},
                {"operation": "compute_column", "config": {"column": "profit", "expression": "amount * 0.5"}},
            ],
        },
    )
    assert pipeline_response.status_code == 201, pipeline_response.text
    pipeline = pipeline_response.json()
    pipeline_id = pipeline["id"]

    run_response = client.post(f"/api/v1/pipelines/{pipeline_id}/run", headers=headers)
    assert run_response.status_code == 200, run_response.text
    run_result = run_response.json()
    assert run_result["status"] == "completed"
    assert run_result["result"]["preview"][0]["customer_name"] == "Alice"
    assert run_result["result"]["preview"][0]["profit"] == 60.0


def test_pipeline_requires_ownership() -> None:
    owner_email = f"owner_pipe_{uuid.uuid4().hex[:8]}@example.com"
    viewer_email = f"viewer_pipe_{uuid.uuid4().hex[:8]}@example.com"
    owner_token = register_user(owner_email)
    viewer_token = register_user(viewer_email)

    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    project_response = client.post(
        "/api/v1/projects",
        headers=owner_headers,
        json={"name": "Restricted Pipeline", "description": "Owner only"},
    )
    project_id = project_response.json()["id"]

    dataset_response = client.post(
        "/api/v1/datasets/upload",
        headers=owner_headers,
        data={"project_id": project_id, "name": "pipeline_data.csv"},
        files={"file": ("pipeline_data.csv", b"customer,amount\nAlice,10\n", "text/csv")},
    )
    dataset_id = dataset_response.json()["id"]

    pipeline_response = client.post(
        "/api/v1/pipelines",
        headers=owner_headers,
        json={
            "name": "Owned Pipeline",
            "dataset_id": dataset_id,
            "steps": [{"operation": "rename_columns", "config": {"mapping": {"customer": "customer_name"}}}],
        },
    )
    pipeline_id = pipeline_response.json()["id"]

    response = client.post(f"/api/v1/pipelines/{pipeline_id}/run", headers=viewer_headers)
    assert response.status_code == 403

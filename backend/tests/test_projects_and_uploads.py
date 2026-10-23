import os
from io import BytesIO
import uuid

import pandas as pd

os.environ["DATABASE_URL"] = "sqlite:///./test_phase3.db"

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def register_user(email: str, password: str = "StrongPass123!") -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Phase Three User",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def test_create_project_and_upload_dataset() -> None:
    email = f"phase3_{uuid.uuid4().hex[:8]}@example.com"
    auth_token = register_user(email)
    headers = {"Authorization": f"Bearer {auth_token}"}

    project_response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Sales Workspace", "description": "Quarterly sales analysis"},
    )

    assert project_response.status_code == 201
    project = project_response.json()
    assert project["name"] == "Sales Workspace"

    dataset_response = client.post(
        "/api/v1/datasets/upload",
        headers=headers,
        data={"project_id": project["id"], "name": "sales.csv"},
        files={"file": ("sales.csv", b"customer,amount\nAlice,120\nAlice,120\nBob,\n", "text/csv")},
    )

    assert dataset_response.status_code == 201, dataset_response.text
    dataset = dataset_response.json()
    assert dataset["name"] == "sales.csv"
    assert dataset["project_id"] == project["id"]
    assert dataset["row_count"] == 3

    list_response = client.get("/api/v1/datasets", headers=headers)
    assert list_response.status_code == 200
    assert any(item["id"] == dataset["id"] for item in list_response.json())


def test_semicolon_csv_with_commas_in_cell_uploads_and_previews() -> None:
    email = f"semicolon_{uuid.uuid4().hex[:8]}@example.com"
    auth_token = register_user(email)
    headers = {"Authorization": f"Bearer {auth_token}"}
    project = client.post("/api/v1/projects", headers=headers, json={"name": "Semicolon Import"}).json()
    csv_content = (
        b"id;name;score;note\n"
        b"1;Alice;10;ok\n"
        b"2;Bob;20;FORMULA= ASSIGNMENT*0,15 +QA*0,15 + TA*0,7\n"
    )

    upload_response = client.post(
        "/api/v1/datasets/upload",
        headers=headers,
        data={"project_id": project["id"]},
        files={"file": ("grades.csv", csv_content, "text/csv")},
    )

    assert upload_response.status_code == 201, upload_response.text
    dataset = upload_response.json()
    assert dataset["row_count"] == 2
    preview_response = client.get(f"/api/v1/datasets/{dataset['id']}/preview", headers=headers)
    assert preview_response.status_code == 200, preview_response.text
    assert preview_response.json()["columns"] == ["id", "name", "score", "note"]
    assert preview_response.json()["rows"][1]["note"] == "FORMULA= ASSIGNMENT*0,15 +QA*0,15 + TA*0,7"


def test_csv_blank_headers_are_not_exposed_as_dataset_columns() -> None:
    email = f"blank_headers_{uuid.uuid4().hex[:8]}@example.com"
    auth_token = register_user(email)
    headers = {"Authorization": f"Bearer {auth_token}"}
    project = client.post("/api/v1/projects", headers=headers, json={"name": "Blank Header Import"}).json()

    upload_response = client.post(
        "/api/v1/datasets/upload",
        headers=headers,
        data={"project_id": project["id"]},
        files={"file": ("blank_headers.csv", b"id,name,,\n1,Alice,teacher note,\n2,Bob,,\n", "text/csv")},
    )

    assert upload_response.status_code == 201, upload_response.text
    assert upload_response.json()["column_count"] == 2
    preview_response = client.get(f"/api/v1/datasets/{upload_response.json()['id']}/preview", headers=headers)
    assert preview_response.status_code == 200, preview_response.text
    assert preview_response.json()["columns"] == ["id", "name"]


def test_dataset_ownership_is_enforced() -> None:
    owner_email = f"owner_{uuid.uuid4().hex[:8]}@example.com"
    viewer_email = f"viewer_{uuid.uuid4().hex[:8]}@example.com"
    owner_token = register_user(owner_email)
    viewer_token = register_user(viewer_email)
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    project_response = client.post(
        "/api/v1/projects",
        headers=owner_headers,
        json={"name": "Restricted Project", "description": "Owner only"},
    )
    project_id = project_response.json()["id"]

    upload_response = client.post(
        "/api/v1/datasets/upload",
        headers=owner_headers,
        data={"project_id": project_id},
        files={"file": ("customer_data.csv", b"customer,amount\nAlice,50\nBob,90\n", "text/csv")},
    )
    dataset_id = upload_response.json()["id"]

    protected_response = client.get(f"/api/v1/datasets/{dataset_id}", headers=viewer_headers)
    assert protected_response.status_code == 403


def test_xlsx_upload_succeeds_and_json_upload_is_rejected() -> None:
    email = f"excel_{uuid.uuid4().hex[:8]}@example.com"
    auth_token = register_user(email)
    headers = {"Authorization": f"Bearer {auth_token}"}
    project = client.post("/api/v1/projects", headers=headers, json={"name": "Excel Import"}).json()

    workbook = BytesIO()
    pd.DataFrame({"name": ["Alice", "Bob"], "amount": [10, 20]}).to_excel(workbook, index=False)
    workbook.seek(0)
    excel_response = client.post(
        "/api/v1/datasets/upload",
        headers=headers,
        data={"project_id": project["id"]},
        files={"file": ("sample.xlsx", workbook.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    json_response = client.post(
        "/api/v1/datasets/upload",
        headers=headers,
        data={"project_id": project["id"]},
        files={"file": ("sample.json", b"[]", "application/json")},
    )

    assert excel_response.status_code == 201, excel_response.text
    assert excel_response.json()["row_count"] == 2
    assert json_response.status_code == 400

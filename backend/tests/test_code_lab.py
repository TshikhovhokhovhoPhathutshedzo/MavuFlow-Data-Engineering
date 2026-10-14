import os
import uuid

os.environ["DATABASE_URL"] = "sqlite:///./test_code_lab.db"

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def create_dataset() -> tuple[dict[str, str], str]:
    email = f"code_lab_{uuid.uuid4().hex[:8]}@example.com"
    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPass123!", "full_name": "Code Lab User"},
    )
    assert register_response.status_code == 201, register_response.text
    headers = {"Authorization": f"Bearer {register_response.json()['access_token']}"}
    project_response = client.post("/api/v1/projects", headers=headers, json={"name": "Manual analysis"})
    assert project_response.status_code == 201, project_response.text
    upload_response = client.post(
        "/api/v1/datasets/upload",
        headers=headers,
        data={"project_id": project_response.json()["id"]},
        files={"file": ("numbers.csv", b"name,amount\nAlice,10\nBob,20\n", "text/csv")},
    )
    assert upload_response.status_code == 201, upload_response.text
    return headers, upload_response.json()["id"]


def test_code_preview_is_not_saved_until_requested() -> None:
    headers, dataset_id = create_dataset()
    code = "df['amount'] = pd.to_numeric(df['amount'])\ndf['doubled'] = np.where(df['amount'] > 10, df['amount'] * 2, df['amount'])"

    preview = client.post(f"/api/v1/datasets/{dataset_id}/code", headers=headers, json={"code": code})
    dataset_after_preview = client.get(f"/api/v1/datasets/{dataset_id}", headers=headers).json()
    saved = client.post(f"/api/v1/datasets/{dataset_id}/code", headers=headers, json={"code": code, "save": True})
    history = client.get(f"/api/v1/datasets/{dataset_id}/versions", headers=headers).json()

    assert preview.status_code == 200, preview.text
    assert preview.json()["saved"] is False
    assert preview.json()["preview"][1]["doubled"] == 40
    assert dataset_after_preview["version"] == 1
    assert saved.status_code == 200, saved.text
    assert saved.json()["saved"] is True
    assert saved.json()["version_number"] == 2
    assert history[0]["operation"] == "manual_code"


def test_code_lab_rejects_imports_and_arbitrary_attributes() -> None:
    headers, dataset_id = create_dataset()

    import_response = client.post(
        f"/api/v1/datasets/{dataset_id}/code",
        headers=headers,
        json={"code": "import os"},
    )
    attribute_response = client.post(
        f"/api/v1/datasets/{dataset_id}/code",
        headers=headers,
        json={"code": "df.to_csv('outside.csv')"},
    )
    missing_column_response = client.post(
        f"/api/v1/datasets/{dataset_id}/code",
        headers=headers,
        json={"code": "df['missing'] = df['unknown'] * 2"},
    )

    assert import_response.status_code == 400
    assert attribute_response.status_code == 400
    assert missing_column_response.status_code == 400
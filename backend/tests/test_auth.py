import os
import uuid

os.environ["DATABASE_URL"] = "sqlite:///./test_auth.db"

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_register_and_login_user() -> None:
    email = f"alice_{uuid.uuid4().hex[:8]}@example.com"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "StrongPass123!",
            "full_name": "Alice Example",
        },
    )

    assert register_response.status_code == 201
    payload = register_response.json()
    assert payload["user"]["email"] == email
    assert "access_token" in payload
    assert "refresh_token" in payload

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "StrongPass123!",
        },
    )

    assert login_response.status_code == 200
    login_payload = login_response.json()
    assert login_payload["user"]["email"] == email
    assert "access_token" in login_payload

    protected_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login_payload['access_token']}"},
    )

    assert protected_response.status_code == 200
    assert protected_response.json()["email"] == email


def test_duplicate_registration_rejected() -> None:
    email = f"alice_duplicate_{uuid.uuid4().hex[:8]}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "StrongPass123!",
            "full_name": "Alice Duplicate",
        },
    )

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "AnotherPass123!",
            "full_name": "Alice Duplicate",
        },
    )

    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


def test_new_login_revokes_previous_session_and_logout_revokes_current() -> None:
    email = f"single_session_{uuid.uuid4().hex[:8]}@example.com"
    credentials = {"email": email, "password": "StrongPass123!", "full_name": "Session User"}
    first_login = client.post("/api/v1/auth/register", json=credentials)
    first_token = first_login.json()["access_token"]

    second_login = client.post(
        "/api/v1/auth/login",
        json={"email": email.upper(), "password": credentials["password"]},
    )
    second_token = second_login.json()["access_token"]

    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {first_token}"}).status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {second_token}"}).status_code == 200
    assert client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {second_token}"}).status_code == 204
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {second_token}"}).status_code == 401


def test_registration_rejects_weak_password_and_invalid_email() -> None:
    weak_password = client.post(
        "/api/v1/auth/register",
        json={"email": "valid@example.com", "password": "weak", "full_name": "Weak User"},
    )
    invalid_email = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "StrongPass123!", "full_name": "Bad Email"},
    )

    assert weak_password.status_code == 422
    assert invalid_email.status_code == 422

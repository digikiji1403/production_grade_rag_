
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.core.security import decode_access_token
from backend.app.db.dependencies import get_db
from backend.app.main import app


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_db, None)


def test_register_user(client):
    email = f"{uuid4().hex}@example.com"

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "RAGForgeTest@2026!",
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["email"] == email
    assert data["is_active"] is True
    assert "id" in data
    assert "hashed_password" not in data
    assert "password" not in data


def test_register_duplicate_email(client):
    email = f"{uuid4().hex}@example.com"
    payload = {
        "email": email,
        "password": "RAGForgeTest@2026!",
    }

    first_response = client.post("/api/v1/auth/register", json=payload)
    second_response = client.post("/api/v1/auth/register", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_login_returns_valid_jwt(client):
    email = f"{uuid4().hex}@example.com"
    password = "RAGForgeTest@2026!"

    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["token_type"] == "bearer"
    assert "access_token" in data

    payload = decode_access_token(data["access_token"])
    assert payload["sub"]


def test_login_rejects_wrong_password(client):
    email = f"{uuid4().hex}@example.com"

    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "RAGForgeTest@2026!",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "WrongPassword@2026!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_register_rejects_short_password(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"{uuid4().hex}@example.com",
            "password": "short",
        },
    )

    assert response.status_code == 422

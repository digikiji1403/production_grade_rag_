
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

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


def create_authenticated_user(client):
    email = f"{uuid4().hex}@example.com"
    password = "RAGForgeTest@2026!"

    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    return {
        "Authorization": f"Bearer {token}"
    }


def test_create_knowledge_base(client):
    headers = create_authenticated_user(client)

    response = client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        json={
            "name": "Machine Learning",
            "description": "Machine learning research notes",
        },
    )

    assert response.status_code == 201
    data = response.json()

    assert data["name"] == "Machine Learning"
    assert data["description"] == "Machine learning research notes"
    assert "id" in data
    assert "owner_id" in data


def test_list_knowledge_bases(client):
    headers = create_authenticated_user(client)

    client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        json={"name": "RAG Research"},
    )

    response = client.get(
        "/api/v1/knowledge-bases",
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "RAG Research"


def test_get_knowledge_base(client):
    headers = create_authenticated_user(client)

    create_response = client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        json={"name": "Deep Learning"},
    )

    knowledge_base_id = create_response.json()["id"]

    response = client.get(
        f"/api/v1/knowledge-bases/{knowledge_base_id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == knowledge_base_id


def test_update_knowledge_base(client):
    headers = create_authenticated_user(client)

    create_response = client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        json={"name": "Old Name"},
    )

    knowledge_base_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/knowledge-bases/{knowledge_base_id}",
        headers=headers,
        json={"name": "New Name"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


def test_delete_knowledge_base(client):
    headers = create_authenticated_user(client)

    create_response = client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        json={"name": "Temporary KB"},
    )

    knowledge_base_id = create_response.json()["id"]

    response = client.delete(
        f"/api/v1/knowledge-bases/{knowledge_base_id}",
        headers=headers,
    )

    assert response.status_code == 204

    get_response = client.get(
        f"/api/v1/knowledge-bases/{knowledge_base_id}",
        headers=headers,
    )

    assert get_response.status_code == 404


def test_user_cannot_access_another_users_knowledge_base(client):
    alice_headers = create_authenticated_user(client)
    bob_headers = create_authenticated_user(client)

    create_response = client.post(
        "/api/v1/knowledge-bases",
        headers=alice_headers,
        json={"name": "Alice Private Research"},
    )

    knowledge_base_id = create_response.json()["id"]

    response = client.get(
        f"/api/v1/knowledge-bases/{knowledge_base_id}",
        headers=bob_headers,
    )

    assert response.status_code == 404


def test_user_cannot_update_another_users_knowledge_base(client):
    alice_headers = create_authenticated_user(client)
    bob_headers = create_authenticated_user(client)

    create_response = client.post(
        "/api/v1/knowledge-bases",
        headers=alice_headers,
        json={"name": "Alice Private Research"},
    )

    knowledge_base_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/knowledge-bases/{knowledge_base_id}",
        headers=bob_headers,
        json={"name": "Hacked"},
    )

    assert response.status_code == 404


def test_user_cannot_delete_another_users_knowledge_base(client):
    alice_headers = create_authenticated_user(client)
    bob_headers = create_authenticated_user(client)

    create_response = client.post(
        "/api/v1/knowledge-bases",
        headers=alice_headers,
        json={"name": "Alice Private Research"},
    )

    knowledge_base_id = create_response.json()["id"]

    response = client.delete(
        f"/api/v1/knowledge-bases/{knowledge_base_id}",
        headers=bob_headers,
    )

    assert response.status_code == 404

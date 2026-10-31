from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.api.v1.routes import query as query_route
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

    return {
        "Authorization": (
            f"Bearer {login_response.json()['access_token']}"
        )
    }


def create_knowledge_base(client, headers, name="Test Knowledge Base"):
    response = client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        json={"name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_query_requires_authentication(client):
    response = client.post(
        f"/api/v1/knowledge-bases/{uuid4()}/query",
        json={"query": "What is RAG?"},
    )

    assert response.status_code == 401


def test_query_rejects_invalid_request(client):
    headers = create_authenticated_user(client)
    knowledge_base_id = create_knowledge_base(client, headers)

    empty_query = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/query",
        headers=headers,
        json={"query": ""},
    )

    invalid_top_k = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/query",
        headers=headers,
        json={"query": "What is RAG?", "top_k": 100},
    )

    assert empty_query.status_code == 422
    assert invalid_top_k.status_code == 422


def test_query_returns_ranked_results(client, monkeypatch):
    headers = create_authenticated_user(client)
    knowledge_base_id = create_knowledge_base(client, headers)

    expected_results = [
        {
            "chunk_id": str(uuid4()),
            "document_id": str(uuid4()),
            "filename": "rag-notes.pdf",
            "chunk_index": 2,
            "content": "Retrieval augmented generation combines retrieval and generation.",
            "page_numbers": [2, 3],
            "extraction_methods": ["pymupdf_native"],
            "score": 0.91,
        }
    ]

    def fake_retrieve_chunks(db, knowledge_base_id, query, top_k):
        assert query == "Explain RAG"
        assert top_k == 5
        return expected_results

    monkeypatch.setattr(
        query_route,
        "retrieve_chunks",
        fake_retrieve_chunks,
    )

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/query",
        headers=headers,
        json={"query": "Explain RAG"},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["query"] == "Explain RAG"
    assert data["knowledge_base_id"] == knowledge_base_id
    assert len(data["results"]) == 1
    assert data["results"][0]["filename"] == "rag-notes.pdf"
    assert data["results"][0]["score"] == pytest.approx(0.91)


def test_user_cannot_query_another_users_knowledge_base(client):
    alice_headers = create_authenticated_user(client)
    bob_headers = create_authenticated_user(client)

    knowledge_base_id = create_knowledge_base(
        client,
        alice_headers,
        "Alice Private Knowledge Base",
    )

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/query",
        headers=bob_headers,
        json={"query": "Private information"},
    )

    assert response.status_code == 404


def test_query_returns_503_when_retrieval_is_unavailable(
    client,
    monkeypatch,
):
    headers = create_authenticated_user(client)
    knowledge_base_id = create_knowledge_base(client, headers)

    def failing_retrieval(*args, **kwargs):
        raise query_route.RetrievalError("Service unavailable")

    monkeypatch.setattr(
        query_route,
        "retrieve_chunks",
        failing_retrieval,
    )

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/query",
        headers=headers,
        json={"query": "Explain RAG"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Retrieval service is temporarily unavailable."
    )

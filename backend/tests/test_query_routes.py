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

    class FakeGenerationService:
        def __init__(self, **kwargs):
            pass

        def generate(self, system_prompt, user_prompt):
            assert "Explain RAG" in user_prompt
            return "RAG combines retrieval and generation [S1]."

        def close(self):
            pass

    monkeypatch.setattr(
        query_route,
        "OllamaGenerationService",
        FakeGenerationService,
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
    assert data["answer"] == "RAG combines retrieval and generation [S1]."
    assert len(data["sources"]) == 1
    assert data["sources"][0]["source_id"] == "S1"
    assert data["sources"][0]["filename"] == "rag-notes.pdf"
    assert data["sources"][0]["page_numbers"] == [2, 3]
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



def test_query_does_not_call_generation_when_no_chunks_are_found(
    client,
    monkeypatch,
):
    headers = create_authenticated_user(client)
    knowledge_base_id = create_knowledge_base(client, headers)

    monkeypatch.setattr(
        query_route,
        "retrieve_chunks",
        lambda **kwargs: [],
    )

    def unexpected_generation(**kwargs):
        raise AssertionError("Generation must not run without evidence.")

    monkeypatch.setattr(
        query_route,
        "OllamaGenerationService",
        unexpected_generation,
    )

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/query",
        headers=headers,
        json={"query": "Question with no matching documents"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["results"] == []
    assert data["sources"] == []
    assert "could not find relevant information" in data["answer"]


def test_query_returns_503_when_generation_fails(client, monkeypatch):
    headers = create_authenticated_user(client)
    knowledge_base_id = create_knowledge_base(client, headers)

    result = {
        "chunk_id": str(uuid4()),
        "document_id": str(uuid4()),
        "filename": "notes.pdf",
        "chunk_index": 0,
        "content": "Relevant evidence.",
        "page_numbers": [1],
        "extraction_methods": ["pymupdf_native"],
        "score": 0.9,
    }

    monkeypatch.setattr(
        query_route,
        "retrieve_chunks",
        lambda **kwargs: [result],
    )

    class FailingGenerationService:
        def __init__(self, **kwargs):
            pass

        def generate(self, **kwargs):
            raise query_route.GenerationError("Internal model error")

        def close(self):
            pass

    monkeypatch.setattr(
        query_route,
        "OllamaGenerationService",
        FailingGenerationService,
    )

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/query",
        headers=headers,
        json={"query": "Explain this"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Answer generation is temporarily unavailable."
    )


def test_query_removes_unknown_citation_ids(client, monkeypatch):
    headers = create_authenticated_user(client)
    knowledge_base_id = create_knowledge_base(client, headers)

    result = {
        "chunk_id": str(uuid4()),
        "document_id": str(uuid4()),
        "filename": "notes.pdf",
        "chunk_index": 0,
        "content": "Relevant evidence.",
        "page_numbers": [1],
        "extraction_methods": ["pymupdf_native"],
        "score": 0.9,
    }

    monkeypatch.setattr(
        query_route,
        "retrieve_chunks",
        lambda **kwargs: [result],
    )

    class FakeGenerationService:
        def __init__(self, **kwargs):
            pass

        def generate(self, **kwargs):
            return "Supported claim [S1]. Unsupported claim [S99]."

        def close(self):
            pass

    monkeypatch.setattr(
        query_route,
        "OllamaGenerationService",
        FakeGenerationService,
    )

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/query",
        headers=headers,
        json={"query": "Explain this"},
    )

    assert response.status_code == 200
    answer = response.json()["answer"]
    assert "[S1]" in answer
    assert "[S99]" not in answer


def test_query_rejects_whitespace_only_question(client):
    headers = create_authenticated_user(client)
    knowledge_base_id = create_knowledge_base(client, headers)

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/query",
        headers=headers,
        json={"query": "    "},
    )

    assert response.status_code == 422

from uuid import uuid4

import pytest

from backend.app.db.models import (
    Document,
    DocumentChunk,
    EvaluationRun,
)
from backend.app.services import evaluation_service
from backend.app.services.retrieval_service import RetrievalError


def create_authenticated_user(client):
    email = f"{uuid4().hex}@example.com"
    password = "RAGForgeTest@2026!"

    register = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert register.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200

    return {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }


def create_knowledge_base(client, headers, name="Evaluation Test KB"):
    response = client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        json={"name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_processed_chunk(db_session, knowledge_base_id):
    document = Document(
        knowledge_base_id=knowledge_base_id,
        filename="evaluation-test.pdf",
        storage_path="test/evaluation-test.pdf",
        content_type="application/pdf",
        size_bytes=100,
        checksum=uuid4().hex + uuid4().hex,
        status="processed",
        page_count=1,
    )
    db_session.add(document)
    db_session.flush()

    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content="Retrieval augmented generation retrieves relevant context.",
        start_page=1,
        end_page=1,
        page_numbers=[1],
        extraction_methods=["test"],
    )
    db_session.add(chunk)
    db_session.flush()

    return chunk


def create_dataset(chunk_id, query_id="query-1"):
    return {
        "dataset_name": "retrieval-benchmark",
        "dataset_version": "1.0",
        "cases": [
            {
                "query_id": query_id,
                "query": "What is retrieval augmented generation?",
                "relevant_chunk_ids": [str(chunk_id)],
                "top_k": 5,
            }
        ],
    }


def fake_retrieval_result(chunk):
    return [
        {
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "filename": "evaluation-test.pdf",
            "chunk_index": 0,
            "content": chunk.content,
            "page_numbers": [1],
            "extraction_methods": ["test"],
            "score": 0.95,
        }
    ]


def test_evaluation_requires_authentication(client):
    response = client.post(
        f"/api/v1/knowledge-bases/{uuid4()}/evaluations",
        json={
            "dataset_name": "test",
            "dataset_version": "1",
            "cases": [],
        },
    )

    assert response.status_code == 401


def test_evaluation_rejects_another_users_knowledge_base(client):
    alice_headers = create_authenticated_user(client)
    bob_headers = create_authenticated_user(client)

    knowledge_base_id = create_knowledge_base(
        client,
        alice_headers,
        "Alice Private KB",
    )

    response = client.get(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/evaluations",
        headers=bob_headers,
    )

    assert response.status_code == 404


def test_create_evaluation_persists_results_and_returns_summary(
    client,
    db_session,
    monkeypatch,
):
    headers = create_authenticated_user(client)
    knowledge_base_id = create_knowledge_base(client, headers)
    chunk = create_processed_chunk(db_session, knowledge_base_id)

    monkeypatch.setattr(
        evaluation_service,
        "retrieve_chunks",
        lambda **kwargs: fake_retrieval_result(chunk),
    )

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/evaluations",
        headers=headers,
        json=create_dataset(chunk.id),
    )

    assert response.status_code == 201

    data = response.json()
    assert data["status"] == "completed"
    assert data["total_queries"] == 1
    assert data["completed_queries"] == 1
    assert data["dataset_name"] == "retrieval-benchmark"
    assert data["aggregate_metrics"]["precision_at_k"] == pytest.approx(0.2)
    assert "error_message" not in data
    assert "results" not in data

    detail = client.get(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/evaluations/{data['id']}",
        headers=headers,
    )

    assert detail.status_code == 200
    detail_data = detail.json()
    assert len(detail_data["results"]) == 1
    assert detail_data["results"][0]["query_id"] == "query-1"
    assert detail_data["results"][0]["retrieved_chunk_ids"] == [
        str(chunk.id)
    ]


def test_evaluation_rejects_invalid_ground_truth(
    client,
    db_session,
):
    headers = create_authenticated_user(client)
    knowledge_base_id = create_knowledge_base(client, headers)

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/evaluations",
        headers=headers,
        json=create_dataset(uuid4()),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Evaluation ground truth contains invalid chunk references."
    )

    runs = db_session.query(EvaluationRun).filter_by(
        knowledge_base_id=knowledge_base_id
    ).all()
    assert runs == []


def test_retrieval_failure_returns_generic_error_and_persists_failed_run(
    client,
    db_session,
    monkeypatch,
):
    headers = create_authenticated_user(client)
    knowledge_base_id = create_knowledge_base(client, headers)
    chunk = create_processed_chunk(db_session, knowledge_base_id)

    def fail_retrieval(**kwargs):
        raise RetrievalError("INTERNAL_RETRIEVAL_SECRET")

    monkeypatch.setattr(
        evaluation_service,
        "retrieve_chunks",
        fail_retrieval,
    )

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/evaluations",
        headers=headers,
        json=create_dataset(chunk.id),
    )

    assert response.status_code == 503
    assert "INTERNAL_RETRIEVAL_SECRET" not in response.text

    run = db_session.query(EvaluationRun).filter_by(
        knowledge_base_id=knowledge_base_id
    ).one()

    assert run.status == "failed"
    assert run.completed_queries == 0
    assert run.error_message == "Evaluation failed (RetrievalError)."
    assert "INTERNAL_RETRIEVAL_SECRET" not in run.error_message


def test_evaluation_history_paginates_and_detail_is_scoped(
    client,
    db_session,
):
    headers = create_authenticated_user(client)
    knowledge_base_id = create_knowledge_base(client, headers)

    runs = [
        EvaluationRun(
            knowledge_base_id=knowledge_base_id,
            dataset_name=f"dataset-{index}",
            dataset_version="1.0",
            status="completed",
            total_queries=1,
            completed_queries=1,
            aggregate_metrics={
                "precision_at_k": 0.5,
                "recall_at_k": 1.0,
                "hit_rate_at_k": 1.0,
                "mrr_at_k": 1.0,
                "ndcg_at_k": 1.0,
            },
        )
        for index in range(3)
    ]

    db_session.add_all(runs)
    db_session.flush()

    response = client.get(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/evaluations?skip=0&limit=2",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["skip"] == 0
    assert data["limit"] == 2
    assert len(data["items"]) == 2

    second_page = client.get(
        f"/api/v1/knowledge-bases/{knowledge_base_id}/evaluations?skip=2&limit=2",
        headers=headers,
    )

    assert second_page.status_code == 200
    assert len(second_page.json()["items"]) == 1

    other_kb_id = create_knowledge_base(
        client,
        headers,
        "Another KB",
    )

    foreign_detail = client.get(
        f"/api/v1/knowledge-bases/{other_kb_id}/evaluations/{runs[0].id}",
        headers=headers,
    )

    assert foreign_detail.status_code == 404
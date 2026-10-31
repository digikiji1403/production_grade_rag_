from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.app.db.models import Document, DocumentChunk, KnowledgeBase, User
from backend.app.services import retrieval_service


class FakeEmbeddingService:
    def __init__(self, **kwargs):
        self.dimensions = kwargs["dimensions"]
        self.closed = False

    def embed_texts(self, texts):
        assert len(texts) == 1
        return [[0.1] * self.dimensions]

    def close(self):
        self.closed = True


class FakeVectorStore:
    points = []

    def __init__(self, **kwargs):
        self.closed = False

    def search(self, query_vector, knowledge_base_id, limit):
        return type(self).points[:limit]

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def mock_external_services(monkeypatch):
    FakeVectorStore.points = []

    monkeypatch.setattr(
        retrieval_service,
        "OllamaEmbeddingService",
        FakeEmbeddingService,
    )
    monkeypatch.setattr(
        retrieval_service,
        "QdrantVectorStore",
        FakeVectorStore,
    )


@pytest.fixture
def knowledge_base(db_session):
    user = User(
        email=f"{uuid4().hex}@example.com",
        hashed_password="test-password-hash",
    )
    db_session.add(user)
    db_session.flush()

    kb = KnowledgeBase(
        owner_id=user.id,
        name="Retrieval Test KB",
        description="Retrieval service tests",
    )
    db_session.add(kb)
    db_session.flush()

    return kb


def create_document(db_session, knowledge_base, status="processed"):
    document = Document(
        knowledge_base_id=knowledge_base.id,
        filename=f"{uuid4().hex}.pdf",
        storage_path="test-document.pdf",
        content_type="application/pdf",
        size_bytes=100,
        checksum=uuid4().hex,
        status=status,
    )
    db_session.add(document)
    db_session.flush()
    return document


def create_chunk(db_session, document, content, chunk_index=0):
    chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=chunk_index,
        content=content,
        start_page=1,
        end_page=2,
        page_numbers=[1, 2],
        extraction_methods=["pymupdf_native"],
    )
    db_session.add(chunk)
    db_session.flush()
    return chunk


def make_point(chunk_id, score):
    return SimpleNamespace(id=str(chunk_id), score=score)


def test_retrieves_processed_document_chunks(
    db_session,
    knowledge_base,
):
    document = create_document(db_session, knowledge_base)
    chunk = create_chunk(
        db_session,
        document,
        "Retrieval augmented generation combines retrieval with generation.",
    )
    db_session.flush()

    FakeVectorStore.points = [make_point(chunk.id, 0.92)]

    results = retrieval_service.retrieve_chunks(
        db=db_session,
        knowledge_base_id=knowledge_base.id,
        query="Explain RAG",
        top_k=5,
    )

    assert len(results) == 1
    assert results[0]["chunk_id"] == chunk.id
    assert results[0]["document_id"] == document.id
    assert results[0]["filename"] == document.filename
    assert results[0]["content"] == chunk.content
    assert results[0]["page_numbers"] == [1, 2]
    assert results[0]["extraction_methods"] == ["pymupdf_native"]
    assert results[0]["score"] == pytest.approx(0.92)


def test_excludes_chunks_from_unprocessed_documents(
    db_session,
    knowledge_base,
):
    document = create_document(
        db_session,
        knowledge_base,
        status="processing",
    )
    chunk = create_chunk(
        db_session,
        document,
        "This document is still being processed.",
    )
    db_session.flush()

    FakeVectorStore.points = [make_point(chunk.id, 0.95)]

    results = retrieval_service.retrieve_chunks(
        db=db_session,
        knowledge_base_id=knowledge_base.id,
        query="Find processing status",
    )

    assert results == []


def test_excludes_chunks_from_another_knowledge_base(
    db_session,
    knowledge_base,
):
    other_user = User(
        email=f"{uuid4().hex}@example.com",
        hashed_password="test-password-hash",
    )
    db_session.add(other_user)
    db_session.flush()

    other_kb = KnowledgeBase(
        owner_id=other_user.id,
        name="Another KB",
    )
    db_session.add(other_kb)
    db_session.flush()

    document = create_document(db_session, other_kb)
    chunk = create_chunk(
        db_session,
        document,
        "This content belongs to another knowledge base.",
    )
    db_session.flush()

    # Simulate a stale or incorrectly scoped vector result.
    FakeVectorStore.points = [make_point(chunk.id, 0.99)]

    results = retrieval_service.retrieve_chunks(
        db=db_session,
        knowledge_base_id=knowledge_base.id,
        query="Find private content",
    )

    assert results == []


def test_excludes_stale_vectors_missing_from_postgresql(
    db_session,
    knowledge_base,
):
    stale_chunk_id = uuid4()

    FakeVectorStore.points = [
        make_point(stale_chunk_id, 0.88)
    ]

    results = retrieval_service.retrieve_chunks(
        db=db_session,
        knowledge_base_id=knowledge_base.id,
        query="Find deleted content",
    )

    assert results == []


def test_preserves_qdrant_ranking_and_scores(
    db_session,
    knowledge_base,
):
    document = create_document(db_session, knowledge_base)

    first_chunk = create_chunk(
        db_session,
        document,
        "First result",
        chunk_index=0,
    )
    second_chunk = create_chunk(
        db_session,
        document,
        "Second result",
        chunk_index=1,
    )
    db_session.flush()

    # Deliberately return the second chunk first.
    FakeVectorStore.points = [
        make_point(second_chunk.id, 0.97),
        make_point(first_chunk.id, 0.81),
    ]

    results = retrieval_service.retrieve_chunks(
        db=db_session,
        knowledge_base_id=knowledge_base.id,
        query="Rank these results",
        top_k=2,
    )

    assert [result["chunk_id"] for result in results] == [
        second_chunk.id,
        first_chunk.id,
    ]
    assert [result["score"] for result in results] == pytest.approx(
        [0.97, 0.81]
    )


def test_returns_empty_list_when_qdrant_finds_nothing(
    db_session,
    knowledge_base,
):
    FakeVectorStore.points = []

    results = retrieval_service.retrieve_chunks(
        db=db_session,
        knowledge_base_id=knowledge_base.id,
        query="No matching content",
    )

    assert results == []

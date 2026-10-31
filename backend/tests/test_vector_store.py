from uuid import uuid4

import pytest

from backend.app.services.vector_store import QdrantVectorStore


@pytest.fixture
def store(tmp_path):
    vector_store = QdrantVectorStore(
        storage_path=str(tmp_path / "qdrant"),
        collection_name="test_chunks",
        vector_size=3,
    )

    yield vector_store

    vector_store.close()


def make_chunk(
    knowledge_base_id=None,
    document_id=None,
    chunk_id=None,
    vector=None,
):
    return {
        "id": chunk_id or uuid4(),
        "document_id": document_id or uuid4(),
        "knowledge_base_id": knowledge_base_id or uuid4(),
        "chunk_index": 0,
        "content": "RAG retrieves relevant document chunks.",
        "page_numbers": [1, 2],
        "extraction_methods": ["pymupdf_native"],
        "vector": vector or [0.1, 0.2, 0.3],
    }


def test_upsert_and_search(store):
    kb_id = uuid4()
    chunk = make_chunk(knowledge_base_id=kb_id)

    store.upsert_chunks([chunk])

    results = store.search(
        query_vector=[0.1, 0.2, 0.3],
        knowledge_base_id=kb_id,
        limit=5,
    )

    assert len(results) == 1
    assert results[0].payload["content"] == chunk["content"]
    assert results[0].payload["page_numbers"] == [1, 2]


def test_search_is_isolated_by_knowledge_base(store):
    kb_one = uuid4()
    kb_two = uuid4()

    store.upsert_chunks([
        make_chunk(knowledge_base_id=kb_one),
        make_chunk(knowledge_base_id=kb_two),
    ])

    results = store.search(
        query_vector=[0.1, 0.2, 0.3],
        knowledge_base_id=kb_one,
    )

    assert len(results) == 1
    assert results[0].payload["knowledge_base_id"] == str(kb_one)


def test_upsert_is_idempotent(store):
    chunk = make_chunk()

    store.upsert_chunks([chunk])
    store.upsert_chunks([chunk])

    results = store.search(
        query_vector=[0.1, 0.2, 0.3],
        knowledge_base_id=chunk["knowledge_base_id"],
    )

    assert len(results) == 1


def test_delete_document_removes_its_chunks(store):
    kb_id = uuid4()
    document_id = uuid4()

    store.upsert_chunks([
        make_chunk(knowledge_base_id=kb_id, document_id=document_id),
        make_chunk(knowledge_base_id=kb_id, document_id=document_id),
        make_chunk(knowledge_base_id=kb_id),
    ])

    store.delete_document(document_id)

    results = store.search(
        query_vector=[0.1, 0.2, 0.3],
        knowledge_base_id=kb_id,
        limit=10,
    )

    assert len(results) == 1


def test_invalid_vector_dimension_is_rejected(store):
    chunk = make_chunk(vector=[0.1, 0.2])

    with pytest.raises(ValueError):
        store.upsert_chunks([chunk])


def test_empty_upsert_is_safe(store):
    store.upsert_chunks([])

    results = store.search(
        query_vector=[0.1, 0.2, 0.3],
        knowledge_base_id=uuid4(),
    )

    assert results == []


def test_invalid_search_limit_is_rejected(store):
    with pytest.raises(ValueError):
        store.search(
            query_vector=[0.1, 0.2, 0.3],
            knowledge_base_id=uuid4(),
            limit=0,
        )

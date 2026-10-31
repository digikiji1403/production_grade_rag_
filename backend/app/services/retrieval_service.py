from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.models import Document, DocumentChunk
from backend.app.services.embedding_service import OllamaEmbeddingService
from backend.app.services.vector_store import QdrantVectorStore


class RetrievalError(Exception):
    """Raised when the retrieval infrastructure is unavailable."""


def retrieve_chunks(
    db: Session,
    knowledge_base_id: UUID,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """Retrieve ranked chunks and validate them against PostgreSQL."""

    settings = get_settings()

    embedding_service = OllamaEmbeddingService(
        base_url=settings.ollama_base_url,
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        batch_size=settings.embedding_batch_size,
        timeout=settings.embedding_timeout_seconds,
    )

    vector_store = None

    try:
        try:
            query_vector = embedding_service.embed_texts([query])[0]

            vector_store = QdrantVectorStore(
                storage_path=settings.qdrant_storage_path,
                collection_name=settings.qdrant_collection_name,
                vector_size=settings.embedding_dimensions,
            )

            points = vector_store.search(
                query_vector=query_vector,
                knowledge_base_id=knowledge_base_id,
                limit=top_k,
            )
        except Exception as exc:
            raise RetrievalError(
                "The retrieval infrastructure is unavailable."
            ) from exc

        if not points:
            return []

        scores = {
            UUID(str(point.id)): float(point.score)
            for point in points
        }

        chunk_ids = list(scores)

        statement = (
            select(DocumentChunk, Document)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(
                DocumentChunk.id.in_(chunk_ids),
                Document.knowledge_base_id == knowledge_base_id,
                Document.status == "processed",
            )
        )

        rows = db.execute(statement).all()

        chunks_by_id = {
            chunk.id: (chunk, document)
            for chunk, document in rows
        }

        # Preserve Qdrant's ranking while excluding stale or invalid records.
        results = []

        for chunk_id in chunk_ids:
            record = chunks_by_id.get(chunk_id)

            if record is None:
                continue

            chunk, document = record

            results.append(
                {
                    "chunk_id": chunk.id,
                    "document_id": document.id,
                    "filename": document.filename,
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "page_numbers": chunk.page_numbers,
                    "extraction_methods": chunk.extraction_methods,
                    "score": scores[chunk_id],
                }
            )

        return results

    finally:
        embedding_service.close()

        if vector_store is not None:
            vector_store.close()

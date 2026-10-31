from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.storage import PROJECT_ROOT
from backend.app.db.models.document import Document
from backend.app.db.models.document_page import DocumentPage
from backend.app.db.models.document_chunk import DocumentChunk
from backend.app.services.document_service.chunking import chunk_pages
from backend.app.services.document_service.extraction import PDFExtractionError, extract_pdf
from backend.app.services.embedding_service import OllamaEmbeddingService
from backend.app.services.vector_store import QdrantVectorStore


def process_document(
    db: Session,
    document_id: UUID,
) -> Document:
    """Extract, chunk, embed, and index a PDF document."""

    document = db.get(Document, document_id)

    if document is None:
        raise ValueError(f"Document not found: {document_id}")

    document.status = "processing"
    document.error_message = None
    db.commit()

    try:
        settings = get_settings()

        result = extract_pdf(
            document.storage_path,
            ocr_enabled=settings.ocr_enabled,
            ocr_language=settings.ocr_language,
            ocr_dpi=settings.ocr_dpi,
        )

        chunks = chunk_pages(
            result.pages,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

        db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document.id
        ).delete(synchronize_session=False)

        db.query(DocumentPage).filter(
            DocumentPage.document_id == document.id
        ).delete(synchronize_session=False)

        db.add_all([
            DocumentPage(
                document_id=document.id,
                page_number=page.page_number,
                text=page.text,
                extraction_method=page.extraction_method,
                ocr_attempted=page.ocr_attempted,
            )
            for page in result.pages
        ])

        chunk_records = [
            DocumentChunk(
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                start_page=chunk.start_page,
                end_page=chunk.end_page,
                page_numbers=chunk.page_numbers,
                extraction_methods=chunk.extraction_methods,
            )
            for chunk in chunks
        ]

        db.add_all(chunk_records)
        db.flush()

        document.page_count = result.page_count
        db.commit()

        embedding_service = OllamaEmbeddingService(
            base_url=settings.ollama_base_url,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
            batch_size=settings.embedding_batch_size,
            timeout=settings.embedding_timeout_seconds,
        )

        try:
            vectors = embedding_service.embed_texts(
                [chunk.content for chunk in chunk_records]
            )
        finally:
            embedding_service.close()

        if len(vectors) != len(chunk_records):
            raise ValueError(
                "Embedding count does not match the number of document chunks."
            )

        qdrant_path = Path(settings.qdrant_storage_path)

        if not qdrant_path.is_absolute():
            qdrant_path = PROJECT_ROOT / qdrant_path

        vector_store = QdrantVectorStore(
            storage_path=str(qdrant_path),
            collection_name=settings.qdrant_collection_name,
            vector_size=settings.embedding_dimensions,
        )

        try:
            vector_store.delete_document(document.id)

            vector_store.upsert_chunks([
                {
                    "id": str(chunk.id),
                    "document_id": str(document.id),
                    "knowledge_base_id": str(document.knowledge_base_id),
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "page_numbers": chunk.page_numbers,
                    "extraction_methods": chunk.extraction_methods,
                    "vector": vector,
                }
                for chunk, vector in zip(chunk_records, vectors)
            ])
        finally:
            vector_store.close()

        document = db.get(Document, document_id)

        if document is None:
            raise ValueError(
                f"Document disappeared during processing: {document_id}"
            )

        document.status = "processed"
        document.error_message = None
        db.commit()
        db.refresh(document)

        return document

    except Exception as exc:
        db.rollback()

        document = db.get(Document, document_id)

        if document is not None:
            document.status = "failed"
            document.error_message = str(exc)[:1000]
            db.commit()

        raise

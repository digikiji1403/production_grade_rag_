import logging
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.storage import PROJECT_ROOT
from backend.app.db.models.document import Document
from backend.app.db.models.job import Job
from backend.app.services.knowledge_base_service import get_knowledge_base
from backend.app.services.vector_store import QdrantVectorStore

logger = logging.getLogger(__name__)


def list_documents(
    db: Session,
    knowledge_base_id: UUID,
    owner_id: UUID,
    skip: int = 0,
    limit: int = 20,
) -> list[Document] | None:
    """List documents belonging to an owned knowledge base."""

    knowledge_base = get_knowledge_base(
        db=db,
        knowledge_base_id=knowledge_base_id,
        owner_id=owner_id,
    )

    if knowledge_base is None:
        return None

    statement = (
        select(Document)
        .where(Document.knowledge_base_id == knowledge_base_id)
        .order_by(Document.created_at.desc(), Document.id.desc())
        .offset(skip)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def get_document(
    db: Session,
    knowledge_base_id: UUID,
    document_id: UUID,
    owner_id: UUID,
) -> Document | None:
    """Retrieve a document only if its knowledge base belongs to the user."""

    knowledge_base = get_knowledge_base(
        db=db,
        knowledge_base_id=knowledge_base_id,
        owner_id=owner_id,
    )

    if knowledge_base is None:
        return None

    statement = select(Document).where(
        Document.id == document_id,
        Document.knowledge_base_id == knowledge_base_id,
    )

    return db.scalar(statement)


def delete_document(
    db: Session,
    knowledge_base_id: UUID,
    document_id: UUID,
    owner_id: UUID,
) -> str | None:
    """
    Delete a document and its related database, vector, and file records.

    Returns:
        None: document or owned knowledge base was not found.
        "processing": a processing job is currently running.
        "deleted": document was deleted.
    """

    knowledge_base = get_knowledge_base(
        db=db,
        knowledge_base_id=knowledge_base_id,
        owner_id=owner_id,
    )

    if knowledge_base is None:
        return None

    try:
        # Use the same document-first lock order as the worker.
        document = db.execute(
            select(Document)
            .where(
                Document.id == document_id,
                Document.knowledge_base_id == knowledge_base_id,
            )
            .with_for_update()
        ).scalar_one_or_none()

        if document is None:
            return None

        jobs = db.scalars(
            select(Job)
            .where(Job.document_id == document.id)
            .with_for_update()
        ).all()

        if any(job.status == "running" for job in jobs):
            db.rollback()
            return "processing"

        storage_path = Path(document.storage_path)

        # Resolve persistent Qdrant storage from the project root.
        settings = get_settings()
        qdrant_path = Path(settings.qdrant_storage_path)

        if not qdrant_path.is_absolute():
            qdrant_path = PROJECT_ROOT / qdrant_path

        # Remove vectors before committing the database deletion.
        # If this fails, the document and PDF remain intact.
        vector_store = QdrantVectorStore(
            storage_path=str(qdrant_path),
            collection_name=settings.qdrant_collection_name,
            vector_size=settings.embedding_dimensions,
        )

        try:
            vector_store.delete_document(document.id)
        finally:
            vector_store.close()

        db.delete(document)
        db.commit()

    except Exception:
        db.rollback()
        raise

    # The database and vector deletion succeeded. Clean up the PDF.
    try:
        storage_path.unlink(missing_ok=True)
    except OSError:
        logger.exception(
            "Could not remove stored file for deleted document %s: %s",
            document_id,
            storage_path,
        )

    return "deleted"

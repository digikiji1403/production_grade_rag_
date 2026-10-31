
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.db.models.document import Document
from backend.app.db.models.job import Job
from backend.app.services.knowledge_base_service import get_knowledge_base
from backend.app.services.document_service.storage import store_document


def upload_document(
    db: Session,
    knowledge_base_id: UUID,
    owner_id: UUID,
    source: BinaryIO,
    filename: str,
    content_type: str,
    max_size_bytes: int | None = None,
) -> Document | None:
    """
    Store a document, persist its metadata, and enqueue processing.

    Returns None if the knowledge base does not exist
    or does not belong to the requesting user.
    """

    # 1. Verify ownership before writing anything to disk.
    knowledge_base = get_knowledge_base(
        db=db,
        knowledge_base_id=knowledge_base_id,
        owner_id=owner_id,
    )

    if knowledge_base is None:
        return None

    # 2. Store the file using bounded-memory, atomic storage.
    stored = store_document(
        source=source,
        original_filename=filename,
        max_size_bytes=max_size_bytes,
    )

    # 3. Prepare the document database record.
    document = Document(
        knowledge_base_id=knowledge_base.id,
        filename=filename,
        storage_path=stored.storage_path,
        content_type=content_type,
        size_bytes=stored.size_bytes,
        checksum=stored.checksum,
        status="uploaded",
    )

    # 4. Prepare a background processing job linked to the document.
    job = Job(
        document=document,
        job_type="document_processing",
        status="pending",
    )

    try:
        # 5. Persist both records in one database transaction.
        db.add(document)
        db.add(job)
        db.commit()

    except Exception:
        # Roll back both database records.
        db.rollback()

        # Compensate for the file already stored on disk.
        Path(stored.storage_path).unlink(missing_ok=True)

        raise

    # 6. Refresh the document after successful commit.
    db.refresh(document)

    return document

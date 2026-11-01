
from pathlib import PurePosixPath
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.dependencies import get_current_user
from backend.app.db.dependencies import get_db
from backend.app.db.models import User, DocumentProcessingRun
from backend.app.schemas.document import DocumentResponse, ProcessingRunResponse
from backend.app.services.document_service.storage import (
    DocumentTooLargeError,
)
from backend.app.services.document_service.upload import upload_document
from backend.app.services.document_service.management import (
    delete_document,
    get_document,
    list_documents,
)

router = APIRouter()


@router.get(
    "/{knowledge_base_id}/documents",
    response_model=list[DocumentResponse],
)
def get_knowledge_base_documents(
    knowledge_base_id: UUID,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if skip < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="skip must be non-negative.",
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit must be between 1 and 100.",
        )

    documents = list_documents(
        db=db,
        knowledge_base_id=knowledge_base_id,
        owner_id=current_user.id,
        skip=skip,
        limit=limit,
    )

    if documents is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found.",
        )

    return documents


@router.get(
    "/{knowledge_base_id}/documents/{document_id}",
    response_model=DocumentResponse,
)
def get_knowledge_base_document(
    knowledge_base_id: UUID,
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = get_document(
        db=db,
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
        owner_id=current_user.id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    return document




@router.get(
    "/{knowledge_base_id}/documents/{document_id}/processing-runs",
    response_model=list[ProcessingRunResponse],
)
def get_document_processing_runs(
    knowledge_base_id: UUID,
    document_id: UUID,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate pagination.
    if skip < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="skip must be non-negative.",
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit must be between 1 and 100.",
        )

    # Verify document existence and ownership before reading telemetry.
    document = get_document(
        db=db,
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
        owner_id=current_user.id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    # Return the most recent attempts first.
    runs = (
        db.query(DocumentProcessingRun)
        .filter(DocumentProcessingRun.document_id == document_id)
        .order_by(
            DocumentProcessingRun.attempt_number.desc(),
            DocumentProcessingRun.started_at.desc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )

    return runs

@router.delete(
    "/{knowledge_base_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_knowledge_base_document(
    knowledge_base_id: UUID,
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = delete_document(
        db=db,
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
        owner_id=current_user.id,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    if result == "processing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a document while it is being processed.",
        )

    return None

@router.post(
    "/{knowledge_base_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def upload_knowledge_base_document(
    knowledge_base_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1. Validate and sanitize the filename.
    filename = (file.filename or "").replace("\\", "/")
    filename = PurePosixPath(filename).name.strip()

    if not filename or len(filename) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename.",
        )

    # 2. Validate the PDF extension.
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF documents are supported.",
        )

    try:
        # 3. Validate the actual PDF signature.
        signature = file.file.read(5)
        file.file.seek(0)

        if signature != b"%PDF-":
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="The uploaded file is not a valid PDF.",
            )

        # 4. Store the document and enqueue background processing.
        document = upload_document(
            db=db,
            knowledge_base_id=knowledge_base_id,
            owner_id=current_user.id,
            source=file.file,
            filename=filename,
            content_type="application/pdf",
            max_size_bytes=get_settings().max_upload_size_bytes,
        )

        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge base not found.",
            )

        return document

    except DocumentTooLargeError:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Document exceeds the configured upload size limit.",
        )

    finally:
        file.file.close()

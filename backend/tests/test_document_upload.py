
import hashlib
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest

from backend.app.db.models.user import User
from backend.app.db.models.knowledge_base import KnowledgeBase
from backend.app.db.models.document import Document
from backend.app.db.models.job import Job
from backend.app.services.document_service.upload import upload_document


@pytest.fixture
def storage_directory(tmp_path, monkeypatch):
    from backend.app.services.document_service import storage

    monkeypatch.setattr(
        storage,
        "DOCUMENT_STORAGE_PATH",
        tmp_path,
    )

    return tmp_path


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
        name="Test Knowledge Base",
        description="Upload service tests",
    )

    db_session.add(kb)
    db_session.flush()

    return user, kb


def test_upload_document_success(
    db_session,
    knowledge_base,
    storage_directory,
):
    user, kb = knowledge_base
    content = b"RAGForge PDF test content"

    document = upload_document(
        db=db_session,
        knowledge_base_id=kb.id,
        owner_id=user.id,
        source=BytesIO(content),
        filename="sample.pdf",
        content_type="application/pdf",
    )

    # Verify document metadata.
    assert document is not None
    assert document.filename == "sample.pdf"
    assert document.knowledge_base_id == kb.id
    assert document.size_bytes == len(content)
    assert document.checksum == hashlib.sha256(content).hexdigest()
    assert document.status == "uploaded"

    # Verify physical file storage.
    saved_file = Path(document.storage_path)

    assert saved_file.exists()
    assert saved_file.read_bytes() == content

    # Verify document persistence.
    persisted_document = db_session.get(Document, document.id)

    assert persisted_document is not None

    # Verify that a processing job was created.
    jobs = (
        db_session.query(Job)
        .filter(Job.document_id == document.id)
        .all()
    )

    assert len(jobs) == 1

    job = jobs[0]

    assert job.document_id == document.id
    assert job.job_type == "document_processing"
    assert job.status == "pending"
    assert job.attempts == 0
    assert job.max_attempts == 3

    # Verify the document-job relationship.
    assert job.document.id == document.id


def test_upload_rejects_another_users_knowledge_base(
    db_session,
    knowledge_base,
    storage_directory,
):
    _, kb = knowledge_base

    another_user = User(
        email=f"{uuid4().hex}@example.com",
        hashed_password="test-password-hash",
    )

    db_session.add(another_user)
    db_session.flush()

    document = upload_document(
        db=db_session,
        knowledge_base_id=kb.id,
        owner_id=another_user.id,
        source=BytesIO(b"private content"),
        filename="private.pdf",
        content_type="application/pdf",
    )

    assert document is None
    assert list(storage_directory.iterdir()) == []


def test_upload_rejects_missing_knowledge_base(
    db_session,
    knowledge_base,
    storage_directory,
):
    user, _ = knowledge_base

    document = upload_document(
        db=db_session,
        knowledge_base_id=uuid4(),
        owner_id=user.id,
        source=BytesIO(b"test content"),
        filename="missing.pdf",
        content_type="application/pdf",
    )

    assert document is None
    assert list(storage_directory.iterdir()) == []


def test_database_failure_removes_stored_file_and_rolls_back_records(
    db_session,
    knowledge_base,
    storage_directory,
    monkeypatch,
):
    user, kb = knowledge_base

    def failing_commit():
        raise RuntimeError("Simulated database failure")

    monkeypatch.setattr(db_session, "commit", failing_commit)

    with pytest.raises(RuntimeError, match="Simulated database failure"):
        upload_document(
            db=db_session,
            knowledge_base_id=kb.id,
            owner_id=user.id,
            source=BytesIO(b"test content"),
            filename="failure.pdf",
            content_type="application/pdf",
        )

    # The stored file must be removed.
    assert list(storage_directory.iterdir()) == []

    # Neither database record should persist.
    documents = (
        db_session.query(Document)
        .filter(Document.filename == "failure.pdf")
        .all()
    )

    jobs = db_session.query(Job).all()

    assert documents == []
    assert jobs == []

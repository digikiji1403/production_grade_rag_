
from uuid import uuid4

import pytest

from backend.app.db.models import User, KnowledgeBase, Document, Job, DocumentProcessingRun


@pytest.fixture
def authenticated_user(client):
    email = f"{uuid4().hex}@example.com"
    password = "RAGForgeTest@2026!"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    return {
        "user": register_response.json(),
        "token": token,
    }


@pytest.fixture
def knowledge_base(db_session, authenticated_user):
    user = (
        db_session.query(User)
        .filter(
            User.email == authenticated_user["user"]["email"]
        )
        .first()
    )

    kb = KnowledgeBase(
        owner_id=user.id,
        name="API Test Knowledge Base",
        description="Document upload API tests",
    )

    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)

    return kb


def test_upload_pdf_success(
    client,
    db_session,
    knowledge_base,
    authenticated_user,
    tmp_path,
    monkeypatch,
):
    from backend.app.services.document_service import storage

    monkeypatch.setattr(
        storage,
        "DOCUMENT_STORAGE_PATH",
        tmp_path,
    )

    pdf_content = b"%PDF-1.4\nRAGForge test PDF content"

    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base.id}/documents",
        files={
            "file": (
                "sample.pdf",
                pdf_content,
                "application/pdf",
            )
        },
        headers={
            "Authorization": (
                f"Bearer {authenticated_user['token']}"
            )
        },
    )

    assert response.status_code == 202

    data = response.json()

    assert data["filename"] == "sample.pdf"
    assert data["knowledge_base_id"] == str(knowledge_base.id)
    assert data["size_bytes"] == len(pdf_content)
    assert data["status"] == "uploaded"
    assert data["checksum"]

    # Verify document persistence.
    document = db_session.get(Document, data["id"])
    assert document is not None

    # Verify that a processing job was created.
    jobs = (
        db_session.query(Job)
        .filter(Job.document_id == document.id)
        .all()
    )

    assert len(jobs) == 1
    assert jobs[0].status == "pending"


def test_upload_requires_authentication(client, knowledge_base):
    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base.id}/documents",
        files={
            "file": (
                "sample.pdf",
                b"%PDF-1.4\ncontent",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 401


def test_upload_rejects_non_pdf_extension(
    client,
    knowledge_base,
):
    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base.id}/documents",
        files={
            "file": (
                "sample.txt",
                b"Some text",
                "text/plain",
            )
        },
    )

    assert response.status_code == 415


def test_upload_rejects_invalid_pdf_signature(
    client,
    knowledge_base,
    authenticated_user,
):
    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base.id}/documents",
        files={
            "file": (
                "fake.pdf",
                b"This is not a PDF",
                "application/pdf",
            )
        },
        headers={
            "Authorization": (
                f"Bearer {authenticated_user['token']}"
            )
        },
    )

    assert response.status_code == 415


def test_upload_rejects_non_pdf_extension(
    client,
    knowledge_base,
    authenticated_user,
):
    response = client.post(
        f"/api/v1/knowledge-bases/{knowledge_base.id}/documents",
        files={
            "file": (
                "sample.txt",
                b"Some text",
                "text/plain",
            )
        },
        headers={
            "Authorization": (
                f"Bearer {authenticated_user['token']}"
            )
        },
    )

    assert response.status_code == 415

def test_upload_rejects_foreign_knowledge_base(
    client,
    db_session,
    authenticated_user,
):
    another_user = User(
        email=f"{uuid4().hex}@example.com",
        hashed_password="test-password-hash",
    )

    db_session.add(another_user)
    db_session.flush()

    foreign_kb = KnowledgeBase(
        owner_id=another_user.id,
        name="Private Knowledge Base",
        description="Belongs to another user",
    )

    db_session.add(foreign_kb)
    db_session.commit()

    response = client.post(
        f"/api/v1/knowledge-bases/{foreign_kb.id}/documents",
        files={
            "file": (
                "sample.pdf",
                b"%PDF-1.4\ncontent",
                "application/pdf",
            )
        },
        headers={
            "Authorization": (
                f"Bearer {authenticated_user['token']}"
            )
        },
    )

    assert response.status_code == 404


def create_test_document(
    db_session,
    knowledge_base,
    tmp_path,
    filename="test.pdf",
    status="uploaded",
):
    """Create a document and a corresponding physical test file."""

    file_path = tmp_path / f"{uuid4().hex}.pdf"
    file_path.write_bytes(b"%PDF-1.4\nTest document")

    document = Document(
        knowledge_base_id=knowledge_base.id,
        filename=filename,
        storage_path=str(file_path),
        content_type="application/pdf",
        size_bytes=file_path.stat().st_size,
        checksum=uuid4().hex,
        status=status,
    )

    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    return document, file_path


def test_list_documents_success(
    client,
    db_session,
    knowledge_base,
    authenticated_user,
    tmp_path,
):
    first, _ = create_test_document(
        db_session, knowledge_base, tmp_path, "first.pdf"
    )
    second, _ = create_test_document(
        db_session, knowledge_base, tmp_path, "second.pdf"
    )

    response = client.get(
        f"/api/v1/knowledge-bases/{knowledge_base.id}/documents",
        headers={
            "Authorization": f"Bearer {authenticated_user['token']}"
        },
    )

    assert response.status_code == 200

    data = response.json()
    returned_ids = {item["id"] for item in data}

    assert str(first.id) in returned_ids
    assert str(second.id) in returned_ids


def test_list_documents_pagination(
    client,
    db_session,
    knowledge_base,
    authenticated_user,
    tmp_path,
):
    for index in range(3):
        create_test_document(
            db_session,
            knowledge_base,
            tmp_path,
            f"document-{index}.pdf",
        )

    response = client.get(
        f"/api/v1/knowledge-bases/{knowledge_base.id}/documents",
        params={"skip": 0, "limit": 2},
        headers={
            "Authorization": f"Bearer {authenticated_user['token']}"
        },
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_document_success(
    client,
    db_session,
    knowledge_base,
    authenticated_user,
    tmp_path,
):
    document, _ = create_test_document(
        db_session, knowledge_base, tmp_path
    )

    response = client.get(
        f"/api/v1/knowledge-bases/{knowledge_base.id}/documents/{document.id}",
        headers={
            "Authorization": f"Bearer {authenticated_user['token']}"
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(document.id)
    assert response.json()["filename"] == document.filename


def test_get_document_not_found(
    client,
    knowledge_base,
    authenticated_user,
):
    missing_id = uuid4()

    response = client.get(
        f"/api/v1/knowledge-bases/{knowledge_base.id}/documents/{missing_id}",
        headers={
            "Authorization": f"Bearer {authenticated_user['token']}"
        },
    )

    assert response.status_code == 404


def test_list_documents_rejects_foreign_knowledge_base(
    client,
    db_session,
    authenticated_user,
):
    another_user = User(
        email=f"{uuid4().hex}@example.com",
        hashed_password="test-password-hash",
    )
    db_session.add(another_user)
    db_session.flush()

    foreign_kb = KnowledgeBase(
        owner_id=another_user.id,
        name="Foreign KB",
        description="Private",
    )
    db_session.add(foreign_kb)
    db_session.commit()

    response = client.get(
        f"/api/v1/knowledge-bases/{foreign_kb.id}/documents",
        headers={
            "Authorization": f"Bearer {authenticated_user['token']}"
        },
    )

    assert response.status_code == 404


def test_delete_document_success(
    client,
    db_session,
    knowledge_base,
    authenticated_user,
    tmp_path,
):
    document, file_path = create_test_document(
        db_session, knowledge_base, tmp_path
    )
    document_id = document.id

    response = client.delete(
        f"/api/v1/knowledge-bases/{knowledge_base.id}/documents/{document_id}",
        headers={
            "Authorization": f"Bearer {authenticated_user['token']}"
        },
    )

    assert response.status_code == 204
    assert db_session.get(Document, document_id) is None
    assert not file_path.exists()


def test_delete_document_while_processing_returns_conflict(
    client,
    db_session,
    knowledge_base,
    authenticated_user,
    tmp_path,
):
    document, file_path = create_test_document(
        db_session, knowledge_base, tmp_path
    )

    running_job = Job(
        document_id=document.id,
        job_type="document_processing",
        status="running",
        attempts=1,
        max_attempts=3,
    )
    db_session.add(running_job)
    db_session.commit()

    response = client.delete(
        f"/api/v1/knowledge-bases/{knowledge_base.id}/documents/{document.id}",
        headers={
            "Authorization": f"Bearer {authenticated_user['token']}"
        },
    )

    assert response.status_code == 409

    # The document and its file must remain intact.
    assert db_session.get(Document, document.id) is not None
    assert file_path.exists()


def test_delete_document_not_found(
    client,
    knowledge_base,
    authenticated_user,
):
    response = client.delete(
        f"/api/v1/knowledge-bases/{knowledge_base.id}/documents/{uuid4()}",
        headers={
            "Authorization": f"Bearer {authenticated_user['token']}"
        },
    )

    assert response.status_code == 404


def create_processing_run(
    db_session,
    document,
    attempt_number,
    status="completed",
    error_stage=None,
):
    run = DocumentProcessingRun(
        document_id=document.id,
        attempt_number=attempt_number,
        status=status,
        current_stage=None,
        stage_timings_ms={
            "extraction": 100,
            "chunking": 50,
            "embedding": 200,
            "vector_indexing": 75,
        },
        page_count=2,
        chunk_count=4,
        embedding_count=4,
        error_stage=error_stage,
        error_message="Simulated failure" if error_stage else None,
        duration_ms=425,
    )

    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    return run


def test_get_document_processing_runs_success(
    client,
    db_session,
    knowledge_base,
    authenticated_user,
    tmp_path,
):
    document, _ = create_test_document(
        db_session, knowledge_base, tmp_path
    )

    run = create_processing_run(
        db_session,
        document,
        attempt_number=1,
    )

    response = client.get(
        f"/api/v1/knowledge-bases/{knowledge_base.id}/documents/{document.id}/processing-runs",
        headers={
            "Authorization": f"Bearer {authenticated_user['token']}"
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["id"] == str(run.id)
    assert data[0]["document_id"] == str(document.id)
    assert data[0]["attempt_number"] == 1
    assert data[0]["status"] == "completed"
    assert data[0]["page_count"] == 2
    assert data[0]["chunk_count"] == 4
    assert data[0]["embedding_count"] == 4
    assert data[0]["duration_ms"] == 425
    assert data[0]["error_stage"] is None
    assert "extraction" in data[0]["stage_timings_ms"]


def test_get_document_processing_runs_requires_authentication(
    client,
    knowledge_base,
    tmp_path,
    db_session,
):
    document, _ = create_test_document(
        db_session, knowledge_base, tmp_path
    )

    response = client.get(
        f"/api/v1/knowledge-bases/{knowledge_base.id}/documents/{document.id}/processing-runs"
    )

    assert response.status_code == 401


def test_get_document_processing_runs_rejects_foreign_document(
    client,
    db_session,
    authenticated_user,
):
    another_user = User(
        email=f"{uuid4().hex}@example.com",
        hashed_password="test-password-hash",
    )
    db_session.add(another_user)
    db_session.flush()

    foreign_kb = KnowledgeBase(
        owner_id=another_user.id,
        name="Foreign KB",
        description="Private",
    )
    db_session.add(foreign_kb)
    db_session.flush()

    foreign_document = Document(
        knowledge_base_id=foreign_kb.id,
        filename="private.pdf",
        storage_path="private.pdf",
        content_type="application/pdf",
        size_bytes=100,
        checksum=uuid4().hex,
        status="processed",
    )
    db_session.add(foreign_document)
    db_session.commit()

    response = client.get(
        f"/api/v1/knowledge-bases/{foreign_kb.id}/documents/{foreign_document.id}/processing-runs",
        headers={
            "Authorization": f"Bearer {authenticated_user['token']}"
        },
    )

    assert response.status_code == 404


def test_get_document_processing_runs_pagination(
    client,
    db_session,
    knowledge_base,
    authenticated_user,
    tmp_path,
):
    document, _ = create_test_document(
        db_session, knowledge_base, tmp_path
    )

    for attempt in range(1, 4):
        create_processing_run(
            db_session,
            document,
            attempt_number=attempt,
        )

    response = client.get(
        f"/api/v1/knowledge-bases/{knowledge_base.id}/documents/{document.id}/processing-runs",
        params={"skip": 1, "limit": 1},
        headers={
            "Authorization": f"Bearer {authenticated_user['token']}"
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["attempt_number"] == 2


def test_get_document_processing_runs_rejects_invalid_pagination(
    client,
    db_session,
    knowledge_base,
    authenticated_user,
    tmp_path,
):
    document, _ = create_test_document(
        db_session, knowledge_base, tmp_path
    )

    response = client.get(
        f"/api/v1/knowledge-bases/{knowledge_base.id}/documents/{document.id}/processing-runs",
        params={"limit": 101},
        headers={
            "Authorization": f"Bearer {authenticated_user['token']}"
        },
    )

    assert response.status_code == 422


from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from backend.app.services.document_service.job_queue import (
    recover_stale_jobs,
)
from backend.app.db.models.user import User
from backend.app.db.models.knowledge_base import KnowledgeBase
from backend.app.db.models.document import Document
from backend.app.db.models.job import Job

from backend.app.services.document_service.job_queue import (
    claim_next_job,
    complete_job,
    calculate_retry_delay,
    retry_job,
    fail_job,
)


def create_test_job(db_session):
    """Create a user, knowledge base, document, and processing job."""

    user = User(
        email=f"job-test-{uuid4()}@example.com",
        hashed_password="test-password-hash",
    )
    db_session.add(user)
    db_session.flush()

    knowledge_base = KnowledgeBase(
        name="Test Knowledge Base",
        owner_id=user.id,
    )
    db_session.add(knowledge_base)
    db_session.flush()

    document = Document(
        knowledge_base_id=knowledge_base.id,
        filename="test.pdf",
        storage_path="test/test.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        checksum="test-checksum",
        status="uploaded",
    )
    db_session.add(document)
    db_session.flush()

    job = Job(
        document_id=document.id,
        job_type="document_processing",
        status="pending",
        attempts=0,
        max_attempts=3,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    return job


# --------------------------------------------------
# Basic job queue tests
# --------------------------------------------------

def test_claim_next_job(db_session):
    job = create_test_job(db_session)

    claimed_job = claim_next_job(db_session)

    assert claimed_job is not None
    assert claimed_job.id == job.id
    assert claimed_job.status == "running"
    assert claimed_job.attempts == 1
    assert claimed_job.locked_at is not None


def test_completed_job_cannot_be_claimed_again(db_session):
    job = create_test_job(db_session)

    claimed_job = claim_next_job(db_session)

    assert claimed_job is not None

    completed_job = complete_job(db_session, job.id)

    assert completed_job.status == "completed"
    assert completed_job.locked_at is None

    next_job = claim_next_job(db_session)

    assert next_job is None


def test_claim_returns_none_when_queue_is_empty(db_session):
    claimed_job = claim_next_job(db_session)

    assert claimed_job is None


# --------------------------------------------------
# Retry delay tests
# --------------------------------------------------

def test_calculate_retry_delay():
    assert calculate_retry_delay(1) == 10
    assert calculate_retry_delay(2) == 20
    assert calculate_retry_delay(3) == 40


def test_calculate_retry_delay_rejects_invalid_attempt():
    with pytest.raises(ValueError):
        calculate_retry_delay(0)


# --------------------------------------------------
# Retry job tests
# --------------------------------------------------

def test_retry_job_schedules_next_attempt(db_session):
    job = create_test_job(db_session)

    job.status = "running"
    job.attempts = 1
    job.locked_at = datetime.now(timezone.utc)
    db_session.commit()

    updated_job = retry_job(
        db_session,
        job.id,
        "Temporary extraction failure",
    )

    assert updated_job.status == "pending"
    assert updated_job.locked_at is None
    assert updated_job.last_error == "Temporary extraction failure"

    now = datetime.now(timezone.utc)

    assert updated_job.available_at >= now + timedelta(seconds=9)


def test_retry_job_marks_job_failed_after_max_attempts(db_session):
    job = create_test_job(db_session)

    job.status = "running"
    job.attempts = job.max_attempts
    db_session.commit()

    updated_job = retry_job(
        db_session,
        job.id,
        "Final processing failure",
    )

    assert updated_job.status == "failed"
    assert updated_job.locked_at is None
    assert updated_job.last_error == "Final processing failure"


# --------------------------------------------------
# Permanent failure tests
# --------------------------------------------------

def test_fail_job_permanently_marks_failure(db_session):
    job = create_test_job(db_session)

    updated_job = fail_job(
        db_session,
        job.id,
        "Unrecoverable error",
    )

    assert updated_job.status == "failed"
    assert updated_job.locked_at is None
    assert updated_job.last_error == "Unrecoverable error"


def test_recover_stale_job(db_session):
    job = create_test_job(db_session)

    job.status = "running"
    job.attempts = 1
    job.locked_at = datetime.now(timezone.utc) - timedelta(
        minutes=10
    )
    db_session.commit()

    recovered_count = recover_stale_jobs(
        db_session,
        timeout_seconds=300,
    )

    db_session.refresh(job)

    assert recovered_count == 1
    assert job.status == "pending"
    assert job.locked_at is None
    assert job.last_error == "Worker lease expired."


def test_recover_stale_job_after_max_attempts(db_session):
    job = create_test_job(db_session)

    job.status = "running"
    job.attempts = job.max_attempts
    job.locked_at = datetime.now(timezone.utc) - timedelta(
        minutes=10
    )
    db_session.commit()

    recovered_count = recover_stale_jobs(
        db_session,
        timeout_seconds=300,
    )

    db_session.refresh(job)

    assert recovered_count == 1
    assert job.status == "failed"
    assert job.locked_at is None


def test_recover_stale_jobs_ignores_recent_jobs(db_session):
    job = create_test_job(db_session)

    job.status = "running"
    job.locked_at = datetime.now(timezone.utc)
    db_session.commit()

    recovered_count = recover_stale_jobs(
        db_session,
        timeout_seconds=300,
    )

    db_session.refresh(job)

    assert recovered_count == 0
    assert job.status == "running"


def test_recover_stale_jobs_rejects_invalid_timeout(db_session):
    with pytest.raises(ValueError):
        recover_stale_jobs(db_session, timeout_seconds=0)


from datetime import timedelta
from uuid import UUID

from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session

from backend.app.db.models.job import Job

from backend.app.db.models.document import Document

def claim_next_job(db: Session) -> Job | None:
    """
    Atomically claim the oldest available pending job.

    Lock order:
    1. Document row
    2. Job row

    Document deletion uses the same lock order.
    SKIP LOCKED allows multiple workers to claim different jobs.
    """

    skipped_job_ids = set()

    while True:
        # Find the oldest eligible job without locking it yet.
        candidate = db.execute(
            select(Job.id, Job.document_id)
            .join(
                Document,
                Document.id == Job.document_id,
            )
            .where(
                Job.status == "pending",
                Job.available_at <= func.now(),
                Job.id.not_in(skipped_job_ids),
            )
            .order_by(Job.created_at.asc())
            .limit(1)
        ).one_or_none()

        if candidate is None:
            return None

        job_id, document_id = candidate

        # Lock the parent document first.
        document = db.execute(
            select(Document.id)
            .where(Document.id == document_id)
            .with_for_update(skip_locked=True)
        ).scalar_one_or_none()

        if document is None:
            skipped_job_ids.add(job_id)
            continue

        # Lock the job second, following the same lock order
        # used by the deletion service.
        job = db.execute(
            select(Job)
            .where(
                Job.id == job_id,
                Job.document_id == document_id,
                Job.status == "pending",
                Job.available_at <= func.now(),
            )
            .with_for_update(skip_locked=True)
        ).scalar_one_or_none()

        if job is None:
            skipped_job_ids.add(job_id)
            continue

        job.status = "running"
        job.attempts += 1
        job.locked_at = func.now()
        job.updated_at = func.now()

        db.commit()
        db.refresh(job)

        return job


def complete_job(db: Session, job_id: UUID) -> Job | None:
    """Mark a successfully processed job as completed."""

    job = db.get(Job, job_id)

    if job is None:
        return None

    job.status = "completed"
    job.locked_at = None
    job.last_error = None
    job.updated_at = func.now()

    db.commit()
    db.refresh(job)

    return job


def calculate_retry_delay(attempts: int) -> int:
    """
    Calculate exponential retry delay in seconds.

    Attempt 1: 10 seconds
    Attempt 2: 20 seconds
    Attempt 3: 40 seconds
    """

    if attempts < 1:
        raise ValueError("Attempts must be at least 1.")

    return 10 * (2 ** (attempts - 1))


def retry_job(
    db: Session,
    job_id: UUID,
    error: str,
) -> Job | None:
    """
    Schedule another attempt if retries remain.

    If the maximum attempts have been reached,
    mark the job as permanently failed.
    """

    job = db.get(Job, job_id)

    if job is None:
        return None

    job.last_error = error[:2000]
    job.locked_at = None
    job.updated_at = func.now()

    if job.attempts >= job.max_attempts:
        job.status = "failed"
    else:
        delay_seconds = calculate_retry_delay(job.attempts)

        job.status = "pending"
        job.available_at = func.now() + timedelta(
            seconds=delay_seconds
        )

    db.commit()
    db.refresh(job)

    return job


def fail_job(
    db: Session,
    job_id: UUID,
    error: str,
) -> Job | None:
    """Permanently mark a job as failed."""

    job = db.get(Job, job_id)

    if job is None:
        return None

    job.status = "failed"
    job.last_error = error[:2000]
    job.locked_at = None
    job.updated_at = func.now()

    db.commit()
    db.refresh(job)

    return job


def recover_stale_jobs(
    db: Session,
    timeout_seconds: int = 300,
) -> int:
    """
    Recover jobs that have remained running beyond their lease.

    Jobs with attempts remaining return to pending.
    Jobs that exhausted their attempts become failed.

    Returns the number of recovered jobs.
    """

    if timeout_seconds < 1:
        raise ValueError("Timeout must be at least 1 second.")

    stale_before = func.now() - timedelta(
        seconds=timeout_seconds
    )

    statement = (
        update(Job)
        .where(
            Job.status == "running",
            Job.locked_at.is_not(None),
            Job.locked_at <= stale_before,
        )
        .values(
            status=case(
                (
                    Job.attempts >= Job.max_attempts,
                    "failed",
                ),
                else_="pending",
            ),
            locked_at=None,
            last_error="Worker lease expired.",
            updated_at=func.now(),
        )
        .returning(Job.id)
    )

    recovered_ids = db.execute(statement).scalars().all()

    db.commit()

    return len(recovered_ids)

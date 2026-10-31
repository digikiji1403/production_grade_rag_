
import logging
import time

from backend.app.db.session import SessionLocal
from backend.app.services.document_service.job_queue import (
    claim_next_job,
    complete_job,
    recover_stale_jobs,
    retry_job,
)
from backend.app.services.document_service.processing import (
    process_document,
)

logger = logging.getLogger(__name__)


def process_next_job() -> bool:
    """
    Claim and process one available document job.

    Each operation uses its own database session.
    Returns True if a job was claimed, otherwise False.
    """

    # Step 1: Claim a job.
    with SessionLocal() as db:
        job = claim_next_job(db)

        if job is None:
            return False

        job_id = job.id
        document_id = job.document_id

    logger.info(
        "Processing job %s for document %s",
        job_id,
        document_id,
    )

    # Step 2: Process the document.
    try:
        with SessionLocal() as db:
            process_document(db, document_id)

    except Exception as exc:
        logger.exception("Job %s failed", job_id)

        # Step 3: Schedule retry or permanent failure.
        with SessionLocal() as db:
            retry_job(
                db,
                job_id,
                str(exc),
            )

        return True

    # Step 4: Mark the job completed.
    with SessionLocal() as db:
        complete_job(db, job_id)

    logger.info("Job %s completed successfully", job_id)

    return True


def run_worker(
    poll_interval: int = 3,
    recovery_interval: int = 60,
) -> None:
    """
    Continuously poll PostgreSQL for pending jobs.
    """

    logger.info("RAGForge worker started")

    last_recovery = 0.0

    while True:
        try:
            current_time = time.monotonic()

            # Periodically recover abandoned jobs.
            if current_time - last_recovery >= recovery_interval:
                with SessionLocal() as db:
                    recovered = recover_stale_jobs(db)

                if recovered:
                    logger.warning(
                        "Recovered %s stale jobs",
                        recovered,
                    )

                last_recovery = current_time

            # Process the next available job.
            processed = process_next_job()

            if not processed:
                time.sleep(poll_interval)

        except KeyboardInterrupt:
            logger.info("Worker shutdown requested")
            break

        except Exception:
            logger.exception("Unexpected worker error")
            time.sleep(poll_interval)

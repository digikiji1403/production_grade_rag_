
from unittest.mock import MagicMock, patch

from backend.app.services.document_service.worker import (
    process_next_job,
)


@patch("backend.app.services.document_service.worker.SessionLocal")
@patch("backend.app.services.document_service.worker.complete_job")
@patch("backend.app.services.document_service.worker.process_document")
@patch("backend.app.services.document_service.worker.claim_next_job")
def test_worker_processes_job_successfully(
    mock_claim,
    mock_process,
    mock_complete,
    mock_session_local,
):
    """A successfully processed document completes its job."""

    job = MagicMock()
    job.id = "test-job-id"
    job.document_id = "test-document-id"

    mock_claim.return_value = job

    mock_db = MagicMock()
    mock_session_local.return_value.__enter__.return_value = mock_db

    result = process_next_job()

    assert result is True
    mock_claim.assert_called_once_with(mock_db)
    mock_process.assert_called_once_with(
        mock_db,
        "test-document-id",
    )
    mock_complete.assert_called_once_with(
        mock_db,
        "test-job-id",
    )


@patch("backend.app.services.document_service.worker.SessionLocal")
@patch("backend.app.services.document_service.worker.retry_job")
@patch("backend.app.services.document_service.worker.process_document")
@patch("backend.app.services.document_service.worker.claim_next_job")
def test_worker_retries_failed_job(
    mock_claim,
    mock_process,
    mock_retry,
    mock_session_local,
):
    """A processing error schedules a retry."""

    job = MagicMock()
    job.id = "test-job-id"
    job.document_id = "test-document-id"

    mock_claim.return_value = job
    mock_process.side_effect = RuntimeError("PDF extraction failed")

    mock_db = MagicMock()
    mock_session_local.return_value.__enter__.return_value = mock_db

    result = process_next_job()

    assert result is True

    mock_retry.assert_called_once_with(
        mock_db,
        "test-job-id",
        "PDF extraction failed",
    )


@patch("backend.app.services.document_service.worker.SessionLocal")
@patch("backend.app.services.document_service.worker.claim_next_job")
def test_worker_returns_false_when_queue_is_empty(
    mock_claim,
    mock_session_local,
):
    """An empty queue does not trigger document processing."""

    mock_claim.return_value = None

    mock_db = MagicMock()
    mock_session_local.return_value.__enter__.return_value = mock_db

    result = process_next_job()

    assert result is False
    mock_claim.assert_called_once_with(mock_db)

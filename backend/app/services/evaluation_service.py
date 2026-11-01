import logging
from datetime import datetime, timezone
from time import perf_counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    Document,
    DocumentChunk,
    EvaluationResult,
    EvaluationRun,
)
from backend.app.schemas.evaluation import EvaluationDataset
from backend.app.services.evaluation_metrics import (
    calculate_retrieval_metrics,
)
from backend.app.services.retrieval_service import (
    RetrievalError,
    retrieve_chunks,
)


logger = logging.getLogger(__name__)


class EvaluationValidationError(ValueError):
    """Raised when evaluation ground truth is invalid."""


EVALUATION_METRIC_NAMES = (
    "precision_at_k",
    "recall_at_k",
    "hit_rate_at_k",
    "mrr_at_k",
    "ndcg_at_k",
)


def _validate_ground_truth(
    db: Session,
    knowledge_base_id: UUID,
    dataset: EvaluationDataset,
) -> None:
    """Validate every relevant chunk before creating an evaluation run."""

    expected_ids = {
        chunk_id
        for case in dataset.cases
        for chunk_id in case.relevant_chunk_ids
    }

    statement = (
        select(DocumentChunk.id)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(
            DocumentChunk.id.in_(expected_ids),
            Document.knowledge_base_id == knowledge_base_id,
            Document.status == "processed",
        )
    )

    valid_ids = set(db.scalars(statement).all())
    invalid_ids = expected_ids - valid_ids

    if invalid_ids:
        raise EvaluationValidationError(
            f"{len(invalid_ids)} ground-truth chunk(s) are missing, "
            "belong to another knowledge base, or are not processed."
        )


def _aggregate_metrics(
    results: list[dict[str, float]],
) -> dict[str, float]:
    """Calculate the arithmetic mean for each retrieval metric."""

    if not results:
        return {name: 0.0 for name in EVALUATION_METRIC_NAMES}

    return {
        name: sum(result[name] for result in results) / len(results)
        for name in EVALUATION_METRIC_NAMES
    }


def run_evaluation(
    db: Session,
    knowledge_base_id: UUID,
    dataset: EvaluationDataset,
) -> EvaluationRun:
    """
    Execute a retrieval-only evaluation against a knowledge base.

    Ground truth is validated before a run is created. Each completed
    query result is committed independently so partial progress survives
    a later retrieval failure.
    """

    _validate_ground_truth(db, knowledge_base_id, dataset)

    run = EvaluationRun(
        knowledge_base_id=knowledge_base_id,
        dataset_name=dataset.dataset_name,
        dataset_version=dataset.dataset_version,
        status="running",
        total_queries=len(dataset.cases),
        completed_queries=0,
        aggregate_metrics={},
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    started = perf_counter()
    completed_metrics = []

    try:
        for case in dataset.cases:
            query_started = perf_counter()

            retrieved = retrieve_chunks(
                db=db,
                knowledge_base_id=knowledge_base_id,
                query=case.query,
                top_k=case.top_k,
            )

            retrieved_ids = [
                item["chunk_id"]
                for item in retrieved
            ]

            metrics = calculate_retrieval_metrics(
                retrieved_chunk_ids=retrieved_ids,
                relevant_chunk_ids=case.relevant_chunk_ids,
                k=case.top_k,
                relevance_grades=(
                    case.relevance_grades or None
                ),
            )

            query_duration = int(
                (perf_counter() - query_started) * 1000
            )

            ranking_details = [
                {
                    "chunk_id": str(item["chunk_id"]),
                    "document_id": str(item["document_id"]),
                    "filename": item["filename"],
                    "chunk_index": item["chunk_index"],
                    "score": item["score"],
                }
                for item in retrieved
            ]

            result = EvaluationResult(
                evaluation_run_id=run.id,
                query_id=case.query_id,
                query=case.query,
                top_k=case.top_k,
                relevant_chunk_ids=[
                    str(value)
                    for value in case.relevant_chunk_ids
                ],
                retrieved_chunk_ids=[
                    str(value)
                    for value in retrieved_ids
                ],
                retrieved_results=ranking_details,
                metrics=metrics,
                duration_ms=query_duration,
            )

            db.add(result)

            # Calculate prospective aggregates before committing.
            prospective_metrics = [
                *completed_metrics,
                metrics,
            ]

            run.completed_queries = len(prospective_metrics)
            run.aggregate_metrics = _aggregate_metrics(
                prospective_metrics
            )

            # Persist each successful query independently.
            db.commit()

            # Only count metrics after the database confirms the commit.
            completed_metrics.append(metrics)

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.duration_ms = int(
            (perf_counter() - started) * 1000
        )
        run.aggregate_metrics = _aggregate_metrics(
            completed_metrics
        )

        db.commit()
        db.refresh(run)

        return run

    except Exception as exc:
        failed_run_id = run.id

        # Failure recording is best-effort. It must never mask the
        # original evaluation exception.
        try:
            db.rollback()

            failed_run = db.get(EvaluationRun, failed_run_id)

            if failed_run is None:
                raise RuntimeError(
                    "Evaluation run could not be reloaded after rollback."
                )

            failed_run.status = "failed"
            failed_run.error_message = (
                f"Evaluation failed ({type(exc).__name__})."
            )
            failed_run.completed_at = datetime.now(timezone.utc)
            failed_run.duration_ms = int(
                (perf_counter() - started) * 1000
            )
            failed_run.aggregate_metrics = _aggregate_metrics(
                completed_metrics
            )

            db.commit()
            db.refresh(failed_run)

        except Exception:
            try:
                db.rollback()
            except Exception:
                logger.exception(
                    "Rollback failed while recording evaluation failure "
                    "for run %s.",
                    failed_run_id,
                )

            logger.exception(
                "Could not persist failed status for evaluation run %s.",
                failed_run_id,
            )

        logger.error(
            "Evaluation run %s failed (%s).",
            failed_run_id,
            type(exc).__name__,
            exc_info=(type(exc), exc, exc.__traceback__),
        )

        raise

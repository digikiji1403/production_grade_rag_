from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.app.core.dependencies import get_current_user
from backend.app.db.dependencies import get_db
from backend.app.db.models import EvaluationRun, User
from backend.app.schemas.evaluation import (
    EvaluationDataset,
    EvaluationHistoryResponse,
    EvaluationRunDetailResponse,
    EvaluationRunResponse,
)
from backend.app.services import knowledge_base_service
from backend.app.services.evaluation_service import (
    EvaluationValidationError,
    run_evaluation,
)
from backend.app.services.retrieval_service import RetrievalError


router = APIRouter()


def _require_knowledge_base(db: Session, knowledge_base_id: UUID, owner_id: UUID):
    knowledge_base = knowledge_base_service.get_knowledge_base(
        db=db,
        knowledge_base_id=knowledge_base_id,
        owner_id=owner_id,
    )

    if knowledge_base is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found.",
        )

    return knowledge_base


@router.post(
    "/{knowledge_base_id}/evaluations",
    response_model=EvaluationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_evaluation(
    knowledge_base_id: UUID,
    dataset: EvaluationDataset,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_knowledge_base(db, knowledge_base_id, current_user.id)

    try:
        return run_evaluation(
            db=db,
            knowledge_base_id=knowledge_base_id,
            dataset=dataset,
        )
    except EvaluationValidationError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Evaluation ground truth contains invalid chunk references.",
        ) from None
    except RetrievalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Retrieval service is temporarily unavailable. The evaluation run was marked as failed.",
        ) from None


@router.get(
    "/{knowledge_base_id}/evaluations",
    response_model=EvaluationHistoryResponse,
)
def list_evaluations(
    knowledge_base_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_knowledge_base(db, knowledge_base_id, current_user.id)

    filters = [EvaluationRun.knowledge_base_id == knowledge_base_id]

    total = db.scalar(
        select(func.count(EvaluationRun.id)).where(*filters)
    ) or 0

    statement = (
        select(EvaluationRun)
        .where(*filters)
        .order_by(EvaluationRun.started_at.desc(), EvaluationRun.id.desc())
        .offset(skip)
        .limit(limit)
    )

    items = list(db.scalars(statement).all())

    return EvaluationHistoryResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{knowledge_base_id}/evaluations/{run_id}",
    response_model=EvaluationRunDetailResponse,
)
def get_evaluation(
    knowledge_base_id: UUID,
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_knowledge_base(db, knowledge_base_id, current_user.id)

    statement = (
        select(EvaluationRun)
        .options(selectinload(EvaluationRun.results))
        .where(
            EvaluationRun.id == run_id,
            EvaluationRun.knowledge_base_id == knowledge_base_id,
        )
    )

    run = db.scalar(statement)

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation run not found.",
        )

    return run
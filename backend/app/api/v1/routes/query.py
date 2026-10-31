from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.db.dependencies import get_db
from backend.app.db.models import User
from backend.app.schemas.query import QueryRequest, QueryResponse
from backend.app.services import knowledge_base_service
from backend.app.services.retrieval_service import (
    RetrievalError,
    retrieve_chunks,
)


router = APIRouter()


@router.post(
    "/{knowledge_base_id}/query",
    response_model=QueryResponse,
)
def query_knowledge_base(
    knowledge_base_id: UUID,
    request: QueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    knowledge_base = knowledge_base_service.get_knowledge_base(
        db,
        knowledge_base_id,
        current_user.id,
    )

    if knowledge_base is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found.",
        )

    try:
        results = retrieve_chunks(
            db=db,
            knowledge_base_id=knowledge_base_id,
            query=request.query,
            top_k=request.top_k,
        )
    except RetrievalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Retrieval service is temporarily unavailable.",
        )

    return QueryResponse(
        query=request.query,
        knowledge_base_id=knowledge_base_id,
        results=results,
    )

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.dependencies import get_current_user
from backend.app.db.dependencies import get_db
from backend.app.db.models import User
from backend.app.schemas.query import QueryRequest, QueryResponse
from backend.app.services import knowledge_base_service
from backend.app.services.generation_service import (
    GenerationError,
    OllamaGenerationService,
)
from backend.app.services.prompt_builder import (
    SYSTEM_PROMPT,
    build_context,
    build_user_prompt,
    filter_unknown_citations,
)
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
        ) from None

    # Do not call the LLM when retrieval found no eligible evidence.
    if not results:
        return QueryResponse(
            query=request.query,
            knowledge_base_id=knowledge_base_id,
            answer=(
                "I could not find relevant information in this "
                "knowledge base to answer your question."
            ),
            sources=[],
            results=[],
        )

    context, sources = build_context(results)
    user_prompt = build_user_prompt(request.query, context)

    settings = get_settings()
    generation_service = None

    try:
        generation_service = OllamaGenerationService(
            base_url=settings.ollama_base_url,
            model=settings.generation_model,
            timeout=settings.generation_timeout_seconds,
            temperature=settings.generation_temperature,
            connect_timeout=settings.generation_connect_timeout_seconds,
        )

        answer = generation_service.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        answer = filter_unknown_citations(answer, sources)

        return QueryResponse(
            query=request.query,
            knowledge_base_id=knowledge_base_id,
            answer=answer,
            sources=sources,
            results=results,
        )

    except GenerationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Answer generation is temporarily unavailable.",
        ) from None

    finally:
        if generation_service is not None:
            try:
                generation_service.close()
            except Exception:
                # Cleanup must not override the API response.
                pass

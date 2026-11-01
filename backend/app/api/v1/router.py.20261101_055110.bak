
from fastapi import APIRouter

from backend.app.api.v1.routes import (
    auth,
    documents,
    health,
    knowledge_bases,
    query,
)

api_router = APIRouter()

api_router.include_router(
    health.router,
    tags=["Health"],
)

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"],
)

api_router.include_router(
    knowledge_bases.router,
    prefix="/knowledge-bases",
    tags=["Knowledge Bases"],
)

api_router.include_router(
    documents.router,
    prefix="/knowledge-bases",
    tags=["Documents"],
)

api_router.include_router(query.router, prefix="/knowledge-bases", tags=["Retrieval"])

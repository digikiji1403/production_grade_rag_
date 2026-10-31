import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api.v1.router import api_router
from backend.app.core.config import get_settings
from backend.app.core.logging import setup_logging


settings = get_settings()

setup_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("RAGForge API started")

    yield

    logger.info("RAGForge API shutting down")


app = FastAPI(
    title=settings.app_name,
    description="Production-oriented multi-document RAG platform",
    version=settings.app_version,
    lifespan=lifespan,
)

app.include_router(
    api_router,
    prefix="/api/v1",
)
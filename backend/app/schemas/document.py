from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    knowledge_base_id: UUID
    filename: str
    content_type: str
    size_bytes: int
    checksum: str
    status: str
    page_count: int | None
    created_at: datetime

class ProcessingRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    attempt_number: int
    status: str
    current_stage: str | None
    stage_timings_ms: dict[str, int | float]
    page_count: int | None
    chunk_count: int | None
    embedding_count: int | None
    error_stage: str | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None

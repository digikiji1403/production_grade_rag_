from uuid import UUID

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10000)
    top_k: int = Field(default=5, ge=1, le=20)


class QueryResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    filename: str
    chunk_index: int
    content: str
    page_numbers: list[int]
    extraction_methods: list[str]
    score: float


class QueryResponse(BaseModel):
    query: str
    knowledge_base_id: UUID
    results: list[QueryResult]

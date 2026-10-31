from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10000)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Query cannot be blank.")
        return value


class QueryResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    filename: str
    chunk_index: int
    content: str
    page_numbers: list[int]
    extraction_methods: list[str]
    score: float


class QuerySource(BaseModel):
    source_id: str
    chunk_id: UUID
    document_id: UUID
    filename: str
    chunk_index: int
    page_numbers: list[int]
    extraction_methods: list[str]
    score: float


class QueryResponse(BaseModel):
    query: str
    knowledge_base_id: UUID
    answer: str
    sources: list[QuerySource]
    results: list[QueryResult]

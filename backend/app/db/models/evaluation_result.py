import uuid

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    query_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    query: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    top_k: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    relevant_chunk_ids: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
    )

    retrieved_chunk_ids: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
    )

    retrieved_results: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    metrics: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    duration_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    evaluation_run = relationship(
        "EvaluationRun",
        back_populates="results",
    )

    __table_args__ = (
        Index(
            "ix_evaluation_results_run_query",
            "evaluation_run_id",
            "query_id",
            unique=True,
        ),
    )

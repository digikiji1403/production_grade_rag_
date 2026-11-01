import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class DocumentProcessingRun(Base):
    __tablename__ = "document_processing_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="running",
        server_default="running",
        index=True,
    )

    current_stage: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # Example: {"extraction": 1200, "chunking": 35, "embedding": 4200}
    stage_timings_ms: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    error_stage: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    document = relationship(
        "Document",
        back_populates="processing_runs",
    )

    __table_args__ = (
        Index(
            "ix_processing_runs_document_attempt",
            "document_id",
            "attempt_number",
        ),
    )

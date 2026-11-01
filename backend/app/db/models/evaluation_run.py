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


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    dataset_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    dataset_version: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="running",
        server_default="running",
        index=True,
    )

    total_queries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    completed_queries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    aggregate_metrics: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
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

    knowledge_base = relationship(
        "KnowledgeBase",
        back_populates="evaluation_runs",
    )

    results = relationship(
        "EvaluationResult",
        back_populates="evaluation_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="EvaluationResult.id",
    )

    __table_args__ = (
        Index(
            "ix_evaluation_runs_kb_created",
            "knowledge_base_id",
            "started_at",
        ),
    )

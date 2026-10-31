
import uuid

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base
from sqlalchemy import Boolean, String, text as sql_text

class DocumentPage(Base):
    __tablename__ = "document_pages"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "page_number",
            name="uq_document_page_number",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    page_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    document = relationship("Document", back_populates="pages")
    extraction_method: Mapped[str] = mapped_column(
    String(30),
    nullable=False,
    default="pymupdf_native",
    server_default="pymupdf_native",
)

    ocr_attempted: Mapped[bool] = mapped_column(
    Boolean,
    nullable=False,
    default=False,
    server_default=sql_text("false"),
)
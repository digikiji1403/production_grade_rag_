"""add OCR metadata to document pages

Revision ID: 45b4d734b552
Revises: b218aaa77e09
Create Date: 2026-10-31 23:12:28.966724

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '45b4d734b552'
down_revision: Union[str, Sequence[str], None] = 'b218aaa77e09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add OCR metadata to document pages."""

    op.add_column(
        "document_pages",
        sa.Column(
            "extraction_method",
            sa.String(length=30),
            server_default="pymupdf_native",
            nullable=False,
        ),
    )

    op.add_column(
        "document_pages",
        sa.Column(
            "ocr_attempted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove OCR metadata from document pages."""

    op.drop_column("document_pages", "ocr_attempted")
    op.drop_column("document_pages", "extraction_method")
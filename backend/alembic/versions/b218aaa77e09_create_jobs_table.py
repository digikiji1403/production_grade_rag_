"""create jobs table

Revision ID: b218aaa77e09
Revises: 46af40e12096
Create Date: 2026-10-31 06:20:08.975428

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b218aaa77e09"
down_revision: Union[str, Sequence[str], None] = "46af40e12096"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the jobs table."""

    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column(
            "job_type",
            sa.String(length=50),
            server_default="document_processing",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "max_attempts",
            sa.Integer(),
            server_default="3",
            nullable=False,
        ),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "locked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Supports looking up jobs belonging to a document.
    op.create_index(
        "ix_jobs_document_id",
        "jobs",
        ["document_id"],
        unique=False,
    )

    # Supports the worker's pending-job lookup.
    op.create_index(
        "ix_jobs_pending_available",
        "jobs",
        ["status", "available_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the jobs table."""

    op.drop_index(
        "ix_jobs_pending_available",
        table_name="jobs",
    )

    op.drop_index(
        "ix_jobs_document_id",
        table_name="jobs",
    )

    op.drop_table("jobs")
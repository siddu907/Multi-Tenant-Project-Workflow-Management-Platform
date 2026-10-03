"""add user token version for access-token revocation

Revision ID: f2a4d8c1e7b9
Revises: c14a7d9b2e31
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a4d8c1e7b9"
down_revision: Union[str, Sequence[str], None] = "c14a7d9b2e31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
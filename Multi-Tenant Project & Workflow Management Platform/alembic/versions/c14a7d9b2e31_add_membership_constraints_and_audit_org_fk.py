"""add membership constraints and audit organization foreign key

Revision ID: c14a7d9b2e31
Revises: 98f0123c3b64
Create Date: 2026-09-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c14a7d9b2e31"
down_revision: Union[str, Sequence[str], None] = "98f0123c3b64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organization_members",
        sa.Column("role", sa.String(length=50), server_default="team_member", nullable=False),
    )
    op.add_column(
        "organization_members",
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.create_index("ix_organization_members_role", "organization_members", ["role"], unique=False)
    op.add_column(
        "project_members",
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.create_unique_constraint(
        "uq_organization_member",
        "organization_members",
        ["organization_id", "user_id"],
    )
    op.create_unique_constraint(
        "uq_project_member",
        "project_members",
        ["project_id", "user_id"],
    )
    op.create_foreign_key(
        "fk_audit_logs_organization_id_organizations",
        "audit_logs",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_audit_logs_organization_id_organizations",
        "audit_logs",
        type_="foreignkey",
    )
    op.drop_constraint("uq_project_member", "project_members", type_="unique")
    op.drop_constraint("uq_organization_member", "organization_members", type_="unique")
    op.drop_index("ix_organization_members_role", table_name="organization_members")
    op.drop_column("project_members", "is_active")
    op.drop_column("organization_members", "is_active")
    op.drop_column("organization_members", "role")

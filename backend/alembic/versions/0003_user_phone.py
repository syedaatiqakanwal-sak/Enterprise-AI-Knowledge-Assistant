"""Add users.phone column — Module 3.

Revision ID: 0003_user_phone
Revises: 0002_auth_rbac
Create Date: 2026-07-20
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_user_phone"
down_revision: Union[str, None] = "0002_auth_rbac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("phone", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "phone")

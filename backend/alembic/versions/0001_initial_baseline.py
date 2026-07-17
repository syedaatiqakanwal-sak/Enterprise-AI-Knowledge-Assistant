"""Initial Alembic baseline — Module 2A Backend Core Infrastructure.

Revision ID: 0001_initial_baseline
Revises:
Create Date: 2026-07-17

This revision establishes the Alembic version table and confirms the async
migration pipeline. Domain tables (users, documents, …) will arrive in
later modules via ``alembic revision --autogenerate``.
"""

from __future__ import annotations

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "0001_initial_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No schema objects yet — baseline only."""
    # Domain models will generate concrete DDL in subsequent revisions.
    pass


def downgrade() -> None:
    """No-op downgrade for the empty baseline."""
    pass

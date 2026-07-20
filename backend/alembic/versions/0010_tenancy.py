"""Alembic migration: Module 11 Multi-Tenant SaaS Administration."""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_tenancy"
down_revision: Union[str, None] = "0009_analytics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("plan", sa.String(32), nullable=False),
        sa.Column("region", sa.String(64), nullable=False),
        sa.Column("settings", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"])

    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("logo_url", sa.String(1024), nullable=True),
        sa.Column("brand_primary", sa.String(32), nullable=True),
        sa.Column("brand_secondary", sa.String(32), nullable=True),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("region", sa.String(64), nullable=False),
        sa.Column("ai_settings", postgresql.JSONB(), nullable=True),
        sa.Column("storage_settings", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_organizations_tenant_id", "organizations", ["tenant_id"])

    op.create_table(
        "teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["manager_id"], ["users.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("role_in_org", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "organization_id", "team_id", name="uq_membership"),
    )

    op.create_table(
        "invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("token", sa.String(128), nullable=False),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("token"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])

    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_prefix", sa.String(32), nullable=False),
        sa.Column("key_hash", sa.String(255), nullable=False),
        sa.Column("scopes", postgresql.JSONB(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "storage_quotas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("documents_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("ocr_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("meetings_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("embeddings_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("images_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("quota_bytes", sa.BigInteger(), nullable=False),
        sa.Column("used_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id"),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("seats", sa.Integer(), nullable=False),
        sa.Column("renews_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id"),
    )

    op.create_table(
        "usage_limits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("max_documents", sa.Integer(), nullable=False),
        sa.Column("max_meetings", sa.Integer(), nullable=False),
        sa.Column("max_ocr", sa.Integer(), nullable=False),
        sa.Column("max_chats", sa.Integer(), nullable=False),
        sa.Column("max_agent_runs", sa.Integer(), nullable=False),
        sa.Column("max_embeddings", sa.Integer(), nullable=False),
        sa.Column("max_storage_bytes", sa.BigInteger(), nullable=False),
        sa.Column("used_documents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used_meetings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used_ocr", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used_chats", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used_agent_runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used_embeddings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id"),
    )

    op.add_column("users", sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("users", sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("users", sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "users",
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_organization_id", "users", ["organization_id"])

    # Seed default tenant + org + workspace + quotas for existing users
    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()
    ws_id = uuid.uuid4()
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO tenants (id, name, slug, status, plan, region, settings)
            VALUES (:id, :name, :slug, 'active', 'enterprise', 'us-east', '{}'::jsonb)
            """
        ),
        {"id": tenant_id, "name": "Default Tenant", "slug": "default"},
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO organizations
              (id, tenant_id, name, timezone, language, region, status, brand_primary)
            VALUES
              (:id, :tid, 'Default Organization', 'UTC', 'en', 'us-east', 'active', '#0ea5e9')
            """
        ),
        {"id": org_id, "tid": tenant_id},
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO workspaces (id, tenant_id, organization_id, name, is_default)
            VALUES (:id, :tid, :oid, 'Default Workspace', true)
            """
        ),
        {"id": ws_id, "tid": tenant_id, "oid": org_id},
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO storage_quotas
              (id, tenant_id, quota_bytes, used_bytes)
            VALUES (:id, :tid, :quota, 0)
            """
        ),
        {"id": uuid.uuid4(), "tid": tenant_id, "quota": 10 * 1024**3},
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO subscriptions (id, tenant_id, plan, status, seats)
            VALUES (:id, :tid, 'enterprise', 'active', 100)
            """
        ),
        {"id": uuid.uuid4(), "tid": tenant_id},
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO usage_limits
              (id, tenant_id, max_documents, max_meetings, max_ocr, max_chats,
               max_agent_runs, max_embeddings, max_storage_bytes)
            VALUES
              (:id, :tid, 10000, 1000, 5000, 50000, 10000, 1000000, :stor)
            """
        ),
        {"id": uuid.uuid4(), "tid": tenant_id, "stor": 10 * 1024**3},
    )
    conn.execute(
        sa.text(
            """
            UPDATE users SET tenant_id = :tid, organization_id = :oid, status = 'active'
            WHERE deleted_at IS NULL
            """
        ),
        {"tid": tenant_id, "oid": org_id},
    )
    user_rows = conn.execute(
        sa.text("SELECT id FROM users WHERE deleted_at IS NULL AND tenant_id = :tid"),
        {"tid": tenant_id},
    ).fetchall()
    for row in user_rows:
        conn.execute(
            sa.text(
                """
                INSERT INTO memberships (id, tenant_id, user_id, organization_id, role_in_org, is_active)
                VALUES (:id, :tid, :uid, :oid, 'member', true)
                """
            ),
            {
                "id": uuid.uuid4(),
                "tid": tenant_id,
                "uid": row[0],
                "oid": org_id,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_column("users", "status")
    op.drop_column("users", "team_id")
    op.drop_column("users", "organization_id")
    op.drop_column("users", "tenant_id")
    op.drop_table("usage_limits")
    op.drop_table("subscriptions")
    op.drop_table("storage_quotas")
    op.drop_table("api_keys")
    op.drop_table("audit_logs")
    op.drop_table("invitations")
    op.drop_table("memberships")
    op.drop_table("workspaces")
    op.drop_table("teams")
    op.drop_table("organizations")
    op.drop_table("tenants")

"""Initial schema with 18 entities and indexes

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-09-16 12:45:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enums definition with create_type=False so create_table won't re-create them
member_role_enum = postgresql.ENUM(
    "OWNER",
    "ADMIN",
    "DEVELOPER",
    "VIEWER",
    name="member_role",
    create_type=False,
)
flag_type_enum = postgresql.ENUM(
    "BOOLEAN",
    "STRING",
    "NUMBER",
    "JSON",
    name="flag_type",
    create_type=False,
)
toggle_kind_enum = postgresql.ENUM(
    "RELEASE",
    "EXPERIMENT",
    "OPS",
    "PERMISSION",
    name="toggle_kind",
    create_type=False,
)
api_key_scope_enum = postgresql.ENUM(
    "SERVER",
    "CLIENT",
    name="api_key_scope",
    create_type=False,
)
config_value_type_enum = postgresql.ENUM(
    "STRING",
    "INT",
    "FLOAT",
    "BOOL",
    "JSON",
    name="config_value_type",
    create_type=False,
)
config_format_enum = postgresql.ENUM(
    "PROPERTIES",
    "JSON",
    "YAML",
    name="config_format",
    create_type=False,
)
change_request_status_enum = postgresql.ENUM(
    "DRAFT",
    "PENDING",
    "APPROVED",
    "REJECTED",
    "APPLIED",
    "CANCELLED",
    name="change_request_status",
    create_type=False,
)


def upgrade() -> None:
    # 1. Create Enums via SQL
    op.execute("CREATE TYPE member_role AS ENUM ('OWNER', 'ADMIN', 'DEVELOPER', 'VIEWER');")
    op.execute("CREATE TYPE flag_type AS ENUM ('BOOLEAN', 'STRING', 'NUMBER', 'JSON');")
    op.execute("CREATE TYPE toggle_kind AS ENUM ('RELEASE', 'EXPERIMENT', 'OPS', 'PERMISSION');")
    op.execute("CREATE TYPE api_key_scope AS ENUM ('SERVER', 'CLIENT');")
    op.execute("CREATE TYPE config_value_type AS ENUM ('STRING', 'INT', 'FLOAT', 'BOOL', 'JSON');")
    op.execute("CREATE TYPE config_format AS ENUM ('PROPERTIES', 'JSON', 'YAML');")
    op.execute(
        "CREATE TYPE change_request_status AS ENUM ("
        "'DRAFT', 'PENDING', 'APPROVED', 'REJECTED', 'APPLIED', 'CANCELLED'"
        ");"
    )

    # 2. Table: organization
    op.create_table(
        "organization",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(60), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("idx_organization_slug", "organization", ["slug"])

    # 3. Table: user
    op.create_table(
        "user",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("idx_user_email", "user", ["email"])

    # 4. Table: membership
    op.create_table(
        "membership",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", member_role_enum, nullable=False),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"),
    )
    op.create_index("idx_membership_user", "membership", ["user_id"])
    op.create_index("idx_membership_org", "membership", ["organization_id"])

    # 5. Table: project
    op.create_table(
        "project",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(60), nullable=False),
        sa.Column("default_stale_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("organization_id", "slug", name="uq_project_org_slug"),
    )
    op.create_index("idx_project_org", "project", ["organization_id"])

    # 6. Table: environment
    op.create_table(
        "environment",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("key", sa.String(60), nullable=False),
        sa.Column("is_production", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("ruleset_version", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("project_id", "key", name="uq_environment_project_key"),
    )
    op.create_index("idx_environment_project", "environment", ["project_id"])

    # 7. Table: api_key
    op.create_table(
        "api_key",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "environment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("environment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("scope", api_key_scope_enum, nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("idx_apikey_env", "api_key", ["environment_id"])
    # Index bắt buộc: idx_apikey_hash (partial index)
    op.create_index(
        "idx_apikey_hash",
        "api_key",
        ["key_hash"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    # 8. Table: flag
    op.create_table(
        "flag",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(160), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("type", flag_type_enum, nullable=False),
        sa.Column("toggle_kind", toggle_kind_enum, nullable=False, server_default="RELEASE"),
        sa.Column("is_temporary", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_client_visible", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("tags", postgresql.ARRAY(sa.String(50)), nullable=False, server_default="{}"),
        sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("project_id", "key", name="uq_flag_project_key"),
        sa.CheckConstraint("key ~ '^[a-zA-Z0-9._-]+$'", name="chk_flag_key_format"),
    )
    # Index bắt buộc: idx_flag_project_key (partial index)
    op.create_index(
        "idx_flag_project_key",
        "flag",
        ["project_id", "key"],
        postgresql_where=sa.text("archived_at IS NULL"),
    )

    # 9. Table: variation
    op.create_table(
        "variation",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "flag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("flag.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("name", sa.String(120), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("flag_id", "key", name="uq_variation_flag_key"),
    )
    op.create_index("idx_variation_flag", "variation", ["flag_id"])

    # 10. Table: flag_environment_setting
    op.create_table(
        "flag_environment_setting",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "flag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("flag.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "environment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("environment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "default_variation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("variation.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "off_variation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("variation.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("bucketing_key", sa.String(60), nullable=False, server_default="userId"),
        sa.Column("last_evaluated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("flag_id", "environment_id", name="uq_fes_flag_env"),
    )
    # Index bắt buộc: idx_fes_env_flag
    op.create_index("idx_fes_env_flag", "flag_environment_setting", ["environment_id", "flag_id"])

    # 11. Table: segment
    op.create_table(
        "segment",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(160), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "conditions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("project_id", "key", name="uq_segment_project_key"),
    )
    # Index bắt buộc: idx_segment_cond_gin (GIN index)
    op.create_index("idx_segment_cond_gin", "segment", ["conditions"], postgresql_using="gin")

    # 12. Table: targeting_rule
    op.create_table(
        "targeting_rule",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "flag_environment_setting_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("flag_environment_setting.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column(
            "segment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("segment.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("conditions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "distribution",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("flag_environment_setting_id", "priority", name="uq_rule_fes_priority"),
    )
    # Index bắt buộc: idx_rule_fes_priority
    op.create_index(
        "idx_rule_fes_priority", "targeting_rule", ["flag_environment_setting_id", "priority"]
    )

    # 13. Table: individual_override
    op.create_table(
        "individual_override",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "flag_environment_setting_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("flag_environment_setting.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("context_key", sa.String(200), nullable=False),
        sa.Column(
            "variation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("variation.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "flag_environment_setting_id", "context_key", name="uq_override_fes_context_key"
        ),
    )
    op.create_index("idx_override_fes", "individual_override", ["flag_environment_setting_id"])

    # 14. Table: config_namespace
    op.create_table(
        "config_namespace",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "environment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("environment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("format", config_format_enum, nullable=False, server_default="JSON"),
        sa.Column("current_release_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("environment_id", "name", name="uq_namespace_env_name"),
    )
    op.create_index("idx_config_ns_env", "config_namespace", ["environment_id"])

    # 15. Table: config_item
    op.create_table(
        "config_item",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "namespace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("config_namespace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("value_type", config_value_type_enum, nullable=False, server_default="STRING"),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("json_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("namespace_id", "key", name="uq_item_namespace_key"),
        sa.CheckConstraint("key ~ '^[a-zA-Z0-9._-]+$'", name="chk_config_item_key_format"),
    )
    op.create_index("idx_config_item_ns", "config_item", ["namespace_id"])

    # 16. Table: config_release
    op.create_table(
        "config_release",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "namespace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("config_namespace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "released_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "released_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "is_rollback_of",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("config_release.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("namespace_id", "version", name="uq_release_namespace_version"),
    )
    op.create_index("idx_config_release_ns", "config_release", ["namespace_id"])

    # Add FK from config_namespace.current_release_id -> config_release.id
    op.create_foreign_key(
        "fk_namespace_current_release",
        "config_namespace",
        "config_release",
        ["current_release_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 17. Table: audit_log (NO deleted_at)
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "environment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("environment.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=True),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    # Indexes bắt buộc: BRIN on created_at and btree on entity
    op.create_index("idx_audit_created_brin", "audit_log", ["created_at"], postgresql_using="brin")
    op.create_index("idx_audit_entity", "audit_log", ["entity_type", "entity_id"])

    # 18. Table: change_request
    op.create_table(
        "change_request",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "environment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("environment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", change_request_status_enum, nullable=False, server_default="DRAFT"),
        sa.Column(
            "requested_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("scheduled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("applied_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("idx_change_request_env", "change_request", ["environment_id"])

    # 19. Table: evaluation_event (PARTITION BY RANGE created_at)
    op.execute(
        """
        CREATE TABLE evaluation_event (
            id BIGSERIAL,
            environment_id UUID NOT NULL REFERENCES environment(id) ON DELETE CASCADE,
            flag_id UUID NOT NULL REFERENCES flag(id) ON DELETE CASCADE,
            variation_id UUID NOT NULL REFERENCES variation(id) ON DELETE CASCADE,
            reason VARCHAR(30) NOT NULL,
            context_key_hash VARCHAR(64) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at);
        """
    )
    # Create default partition so inserts outside specific ranges succeed
    op.execute(
        """
        CREATE TABLE evaluation_event_default PARTITION OF evaluation_event DEFAULT;
        """
    )


def downgrade() -> None:
    # Drop partitioned table and default partition
    op.execute("DROP TABLE IF EXISTS evaluation_event CASCADE;")

    # Drop tables in reverse topological order
    op.drop_table("change_request")
    op.drop_table("audit_log")

    # Drop circular FK between config_namespace and config_release
    op.drop_constraint("fk_namespace_current_release", "config_namespace", type_="foreignkey")
    op.drop_table("config_release")
    op.drop_table("config_item")
    op.drop_table("config_namespace")

    op.drop_table("individual_override")
    op.drop_table("targeting_rule")
    op.drop_table("segment")
    op.drop_table("flag_environment_setting")
    op.drop_table("variation")
    op.drop_table("flag")

    op.drop_table("api_key")
    op.drop_table("environment")
    op.drop_table("project")
    op.drop_table("membership")
    op.drop_table("user")
    op.drop_table("organization")

    # Drop enums via SQL
    op.execute("DROP TYPE IF EXISTS change_request_status;")
    op.execute("DROP TYPE IF EXISTS config_format;")
    op.execute("DROP TYPE IF EXISTS config_value_type;")
    op.execute("DROP TYPE IF EXISTS api_key_scope;")
    op.execute("DROP TYPE IF EXISTS toggle_kind;")
    op.execute("DROP TYPE IF EXISTS flag_type;")
    op.execute("DROP TYPE IF EXISTS member_role;")

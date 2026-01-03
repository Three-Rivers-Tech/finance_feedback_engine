"""V001: Initial authentication schema

Revision ID: 001_initial_auth_schema
Revises:
Create Date: 2026-01-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial_auth_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial authentication tables."""

    # API Keys table
    op.create_table(
        'api_keys',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('key_hash', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('rate_limit_per_minute', sa.Integer(), nullable=False, server_default=sa.literal(100)),
        sa.Column('description', sa.Text(), nullable=True),
    )

    # Authentication audit log
    op.create_table(
        'auth_audit',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('api_key_id', sa.String(36), sa.ForeignKey('api_keys.id', ondelete='CASCADE'), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(255), nullable=True),
        sa.Column('endpoint', sa.String(255), nullable=True),
        sa.Column('method', sa.String(10), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
    )

    # Create indexes
    op.create_index('ix_auth_audit_timestamp', 'auth_audit', ['timestamp'])
    op.create_index('ix_auth_audit_api_key_id', 'auth_audit', ['api_key_id'])


def downgrade() -> None:
    """Drop authentication tables."""
    op.drop_table('auth_audit')
    op.drop_table('api_keys')

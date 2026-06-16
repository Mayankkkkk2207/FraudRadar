"""initial schema

Revision ID: 202606160001
Revises:
Create Date: 2026-06-16 00:01:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "202606160001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "transaction_scores",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("transaction_id", sa.String(length=96), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("merchant", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("card_id", sa.String(length=96), nullable=False),
        sa.Column("customer_id", sa.String(length=96), nullable=False),
        sa.Column("country", sa.String(length=16), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("is_fraud", sa.Boolean(), nullable=False),
        sa.Column("isolation_forest_score", sa.Float(), nullable=False),
        sa.Column("isolation_forest_anomaly", sa.Float(), nullable=False),
        sa.Column("autoencoder_mse", sa.Float(), nullable=False),
        sa.Column("autoencoder_anomaly", sa.Float(), nullable=False),
        sa.Column("reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("features", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("scorer_version", sa.String(length=32), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transaction_scores_created_at", "transaction_scores", ["created_at"], unique=False)
    op.create_index("ix_transaction_scores_risk_level", "transaction_scores", ["risk_level"], unique=False)
    op.create_index("ix_transaction_scores_transaction_id", "transaction_scores", ["transaction_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_transaction_scores_transaction_id", table_name="transaction_scores")
    op.drop_index("ix_transaction_scores_risk_level", table_name="transaction_scores")
    op.drop_index("ix_transaction_scores_created_at", table_name="transaction_scores")
    op.drop_table("transaction_scores")

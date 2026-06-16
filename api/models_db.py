from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class TransactionScore(Base):
    __tablename__ = "transaction_scores"
    __table_args__ = (
        Index("ix_transaction_scores_created_at", "created_at"),
        Index("ix_transaction_scores_risk_level", "risk_level"),
        Index("ix_transaction_scores_transaction_id", "transaction_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id: Mapped[str] = mapped_column(String(96), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    merchant: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    card_id: Mapped[str] = mapped_column(String(96), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(96), nullable=False)
    country: Mapped[str] = mapped_column(String(16), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    device_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    is_fraud: Mapped[bool] = mapped_column(Boolean, nullable=False)
    isolation_forest_score: Mapped[float] = mapped_column(Float, nullable=False)
    isolation_forest_anomaly: Mapped[float] = mapped_column(Float, nullable=False)
    autoencoder_mse: Mapped[float] = mapped_column(Float, nullable=False)
    autoencoder_anomaly: Mapped[float] = mapped_column(Float, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    features: Mapped[dict[str, float]] = mapped_column(JSONB, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    scorer_version: Mapped[str] = mapped_column(String(32), nullable=False, default="0.1.0")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(tz=timezone.utc),
    )


class FailedTransaction(Base):
    """Transactions that failed to be scored."""
    __tablename__ = "failed_transactions"
    __table_args__ = (
        Index("ix_failed_transactions_transaction_id", "transaction_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    error_msg: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(tz=timezone.utc),
    )

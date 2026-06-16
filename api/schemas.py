from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from fraudradar.features import FEATURE_COLUMNS


class TransactionIn(BaseModel):
    """Input schema for scoring a single transaction."""
    transaction_id: str = Field(..., min_length=1, max_length=96)
    timestamp: datetime | None = None
    amount: float = Field(..., ge=0)
    currency: str = Field("USD", min_length=3, max_length=8)
    merchant: str = Field(..., min_length=1, max_length=160)
    category: str = Field("retail", min_length=1, max_length=80)
    card_id: str = Field(..., min_length=1, max_length=96)
    customer_id: str = Field(..., min_length=1, max_length=96)
    country: str = Field("US", min_length=2, max_length=16)
    ip_address: str = ""
    device_id: str = ""
    features: dict[str, float] = Field(default_factory=dict)

    def normalized_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload["features"] = {column: float(payload["features"].get(column, 0.0)) for column in FEATURE_COLUMNS}
        payload["features"]["Amount"] = float(self.amount)
        return payload


class TransactionOut(BaseModel):
    """Output schema for a single transaction with fraud scores."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    transaction_id: str
    timestamp: datetime
    amount: float
    currency: str
    merchant: str
    category: str
    card_id: str
    customer_id: str
    country: str
    ip_address: str
    device_id: str
    risk_score: float
    risk_level: Literal["low", "medium", "high"]
    is_fraud: bool
    isolation_forest_score: float
    isolation_forest_anomaly: float
    autoencoder_mse: float
    autoencoder_anomaly: float
    reasons: list[str]
    features: dict[str, float]
    created_at: datetime


class FraudScoreResponse(BaseModel):
    """Response from scoring a transaction."""
    model_config = ConfigDict(from_attributes=True)

    transaction_id: str
    risk_score: float
    risk_level: Literal["low", "medium", "high"]
    is_fraud: bool
    isolation_forest_score: float
    isolation_forest_anomaly: float
    autoencoder_mse: float
    autoencoder_anomaly: float
    reasons: list[str]
    scored_at: datetime


class PaginatedTransactions(BaseModel):
    """Paginated list of transactions."""
    items: list[TransactionOut]
    total: int
    page: int
    limit: int
    pages: int


class StatsResponse(BaseModel):
    """Statistics response."""
    total_transactions: int
    fraud_detected: int
    fraud_rate_percent: float
    avg_fraud_probability: float
    risk_breakdown: dict[str, int]  # { "LOW": int, "MEDIUM": int, "HIGH": int, "CRITICAL": int }
    top_fraud_merchants: list[dict[str, Any]]  # [{"merchant_name": str, "count": int}]
    transactions_last_hour: int
    fraud_last_hour: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: Literal["ok", "degraded", "error"]
    kafka: Literal["ok", "error"]
    postgres: Literal["ok", "error"]
    redis: Literal["ok", "error"]
    models: Literal["ok", "error"]
    timestamp: datetime


class FailedTransactionOut(BaseModel):
    """Output schema for a failed transaction."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_id: str | None
    raw_payload: dict
    error_msg: str
    created_at: datetime

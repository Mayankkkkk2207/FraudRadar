from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, MetaData, String, Table, Text, create_engine
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.engine import Engine
from sqlalchemy.sql import func


load_dotenv()


def database_url() -> str:
    explicit_url = os.getenv("DATABASE_URL")
    if explicit_url:
        return explicit_url

    user = os.getenv("POSTGRES_USER", "fraudradar")
    password = os.getenv("POSTGRES_PASSWORD", "fraudradar")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "fraudradar")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


engine: Engine = create_engine(
    database_url(),
    pool_pre_ping=True,
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
    future=True,
)
metadata = MetaData()

transactions = Table(
    "transactions",
    metadata,
    Column("transaction_id", String(128), primary_key=True),
    Column("user_id", String(128), nullable=True),
    Column("merchant_id", String(128), nullable=True),
    Column("merchant_name", String(255), nullable=True),
    Column("merchant_category", String(128), nullable=True),
    Column("amount", Float, nullable=True),
    Column("currency", String(16), nullable=True),
    Column("risk_level", String(32), nullable=False),
    Column("is_fraud", Boolean, nullable=False),
    Column("combined_fraud_probability", Float, nullable=True),
    Column("isolation_forest_score", Float, nullable=True),
    Column("autoencoder_score", Float, nullable=True),
    Column("payload", JSONB, nullable=False),
    Column("scored_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
)

failed_transactions = Table(
    "failed_transactions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("transaction_id", String(128), nullable=True, index=True),
    Column("payload", JSONB, nullable=False),
    Column("error_msg", Text, nullable=False),
    Column("failed_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)


def init_db(max_attempts: int = 40, delay_seconds: float = 1.5) -> None:
    last_error: Exception | None = None
    for _attempt in range(1, max_attempts + 1):
        try:
            metadata.create_all(bind=engine)
            return
        except Exception as exc:
            last_error = exc
            time.sleep(delay_seconds)
    raise RuntimeError("PostgreSQL did not become ready") from last_error


def parse_scored_at(result_dict: dict[str, Any]) -> datetime:
    raw_value = result_dict.get("scored_at")
    if isinstance(raw_value, datetime):
        return raw_value if raw_value.tzinfo else raw_value.replace(tzinfo=timezone.utc)
    if isinstance(raw_value, str):
        try:
            parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(tz=timezone.utc)


def optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def row_from_result(result_dict: dict[str, Any]) -> dict[str, Any]:
    transaction_id = result_dict.get("transaction_id")
    if not transaction_id:
        raise ValueError("Cannot write transaction without transaction_id")

    return {
        "transaction_id": str(transaction_id),
        "user_id": result_dict.get("user_id"),
        "merchant_id": result_dict.get("merchant_id"),
        "merchant_name": result_dict.get("merchant_name"),
        "merchant_category": result_dict.get("merchant_category"),
        "amount": optional_float(result_dict.get("amount")),
        "currency": result_dict.get("currency"),
        "risk_level": str(result_dict.get("risk_level", "UNKNOWN")),
        "is_fraud": bool(result_dict.get("is_fraud", False)),
        "combined_fraud_probability": optional_float(result_dict.get("combined_fraud_probability")),
        "isolation_forest_score": optional_float(result_dict.get("isolation_forest_score")),
        "autoencoder_score": optional_float(result_dict.get("autoencoder_score")),
        "payload": result_dict,
        "scored_at": parse_scored_at(result_dict),
        "updated_at": datetime.now(tz=timezone.utc),
    }


def upsert_transaction(result_dict: dict[str, Any]) -> None:
    row = row_from_result(result_dict)
    stmt = insert(transactions).values(**row)
    update_values = {
        column.name: getattr(stmt.excluded, column.name)
        for column in transactions.c
        if column.name not in {"transaction_id", "created_at"}
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=[transactions.c.transaction_id],
        set_=update_values,
    )

    with engine.begin() as connection:
        connection.execute(stmt)


def write_failed(transaction_dict: dict[str, Any], error_msg: str) -> None:
    row = {
        "transaction_id": transaction_dict.get("transaction_id"),
        "payload": transaction_dict,
        "error_msg": error_msg,
    }
    with engine.begin() as connection:
        connection.execute(failed_transactions.insert().values(**row))

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import and_, case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models_db import TransactionScore
from api.schemas import HealthResponse, StatsResponse
from fraudradar.scoring import FraudScorer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stats"])


async def check_kafka() -> bool:
    """Check Kafka connectivity."""
    try:
        # Try to import and check Kafka
        from kafka import KafkaProducer
        from kafka.errors import NoBrokersAvailable
        
        producer = KafkaProducer(
            bootstrap_servers="localhost:9092",
            request_timeout_ms=5000,
            api_version_auto_timeout_ms=5000,
        )
        producer.close()
        return True
    except Exception as e:
        logger.warning(f"Kafka check failed: {e}")
        return False


async def check_postgres(db: AsyncSession) -> bool:
    """Check PostgreSQL connectivity."""
    try:
        await db.execute(select(1))
        return True
    except Exception as e:
        logger.warning(f"PostgreSQL check failed: {e}")
        return False


async def check_redis() -> bool:
    """Check Redis connectivity."""
    try:
        import redis
        r = redis.Redis.from_url("redis://localhost:6379/0", socket_connect_timeout=5)
        r.ping()
        return True
    except Exception as e:
        logger.warning(f"Redis check failed: {e}")
        return False


async def check_models() -> bool:
    """Check if ML models are available."""
    try:
        scorer = FraudScorer()
        scorer.load()
        return True
    except Exception as e:
        logger.warning(f"Models check failed: {e}")
        return False


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)) -> StatsResponse:
    """
    Get comprehensive fraud statistics.
    
    Returns:
    - total_transactions: Total number of transactions processed
    - fraud_detected: Number of transactions marked as fraud
    - fraud_rate_percent: Percentage of transactions marked as fraud
    - avg_fraud_probability: Average risk score across all transactions
    - risk_breakdown: Count of transactions by risk level
    - top_fraud_merchants: Top merchants by fraud count
    - transactions_last_hour: Transactions in the last hour
    - fraud_last_hour: Fraudulent transactions in the last hour
    """
    # Total stats
    total_result = await db.execute(select(func.count(TransactionScore.id)))
    total = int(total_result.scalar() or 0)
    
    # Fraud count and avg score
    fraud_result = await db.execute(
        select(
            func.sum(case((TransactionScore.is_fraud.is_(True), 1), else_=0)),
            func.avg(TransactionScore.risk_score),
        )
    )
    fraud_count, avg_score = fraud_result.one()
    fraud_count = int(fraud_count or 0)
    avg_score = float(avg_score or 0.0)
    
    # Risk breakdown
    breakdown_result = await db.execute(
        select(
            TransactionScore.risk_level,
            func.count(TransactionScore.id),
        ).group_by(TransactionScore.risk_level)
    )
    risk_breakdown = {row[0].upper(): int(row[1]) for row in breakdown_result.all()}
    # Ensure all levels are present
    for level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
        risk_breakdown.setdefault(level, 0)
    
    # Top fraud merchants
    merchants_result = await db.execute(
        select(
            TransactionScore.merchant,
            func.count(TransactionScore.id).label("count"),
        )
        .where(TransactionScore.is_fraud.is_(True))
        .group_by(TransactionScore.merchant)
        .order_by(desc("count"))
        .limit(10)
    )
    top_merchants = [
        {"merchant_name": row[0], "count": row[1]}
        for row in merchants_result.all()
    ]
    
    # Last hour stats
    one_hour_ago = datetime.now(tz=timezone.utc) - timedelta(hours=1)
    last_hour_result = await db.execute(
        select(
            func.count(TransactionScore.id),
            func.sum(case((TransactionScore.is_fraud.is_(True), 1), else_=0)),
        ).where(TransactionScore.created_at >= one_hour_ago)
    )
    last_hour_total, last_hour_fraud = last_hour_result.one()
    last_hour_total = int(last_hour_total or 0)
    last_hour_fraud = int(last_hour_fraud or 0)
    
    fraud_rate = (fraud_count / total * 100) if total > 0 else 0.0
    
    return StatsResponse(
        total_transactions=total,
        fraud_detected=fraud_count,
        fraud_rate_percent=round(fraud_rate, 2),
        avg_fraud_probability=round(avg_score, 2),
        risk_breakdown=risk_breakdown,
        top_fraud_merchants=top_merchants,
        transactions_last_hour=last_hour_total,
        fraud_last_hour=last_hour_fraud,
    )


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """
    Health check endpoint.
    
    Verifies connectivity to all critical services:
    - kafka: Kafka broker
    - postgres: PostgreSQL database
    - redis: Redis cache
    - models: ML models are loaded
    
    Returns "ok" if all services are healthy, "degraded" if some services are down.
    """
    postgres_ok = await check_postgres(db)
    kafka_ok = await check_kafka()
    redis_ok = await check_redis()
    models_ok = await check_models()
    
    # Overall status
    all_ok = postgres_ok and kafka_ok and redis_ok and models_ok
    status = "ok" if all_ok else "degraded" if postgres_ok else "error"
    
    return HealthResponse(
        status=status,
        kafka="ok" if kafka_ok else "error",
        postgres="ok" if postgres_ok else "error",
        redis="ok" if redis_ok else "error",
        models="ok" if models_ok else "error",
        timestamp=datetime.now(tz=timezone.utc),
    )

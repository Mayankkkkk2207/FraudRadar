from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None or value == "" else int(value)


def _float(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value is None or value == "" else float(value)


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "FraudRadar")
    environment: str = os.getenv("ENVIRONMENT", "local")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    kafka_raw_topic: str = os.getenv("KAFKA_RAW_TOPIC", "transactions.raw")
    kafka_scored_topic: str = os.getenv("KAFKA_SCORED_TOPIC", "transactions.scored")
    kafka_consumer_group: str = os.getenv("KAFKA_CONSUMER_GROUP", "fraudradar-scorers")

    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://fraudradar:fraudradar@localhost:5432/fraudradar",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    model_dir: Path = Path(os.getenv("MODEL_DIR", "models")).resolve()
    data_dir: Path = Path(os.getenv("DATA_DIR", "data")).resolve()
    random_seed: int = _int("RANDOM_SEED", 42)

    simulator_interval_seconds: float = _float("SIMULATOR_INTERVAL_SECONDS", 0.2)
    simulator_burst_size: int = _int("SIMULATOR_BURST_SIZE", 1)
    simulator_fraud_rate: float = _float("SIMULATOR_FRAUD_RATE", 0.035)

    high_risk_threshold: float = _float("HIGH_RISK_THRESHOLD", 75.0)
    medium_risk_threshold: float = _float("MEDIUM_RISK_THRESHOLD", 45.0)


settings = Settings()

from __future__ import annotations

import json
import logging
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import redis
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError, NoBrokersAvailable
from prometheus_client import Counter, Histogram, start_http_server

from training import score_utils

try:
    from db_writer import init_db, upsert_transaction, write_failed
except ImportError:  # pragma: no cover - supports python -m consumer.scorer
    from consumer.db_writer import init_db, upsert_transaction, write_failed


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TRANSACTIONS_TOPIC = os.getenv("KAFKA_TRANSACTIONS_TOPIC", "transactions")
FRAUD_SCORES_TOPIC = os.getenv("KAFKA_FRAUD_SCORES_TOPIC", "fraud_scores")
CONSUMER_GROUP = "fraud-scorer-group"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
METRICS_PORT = int(os.getenv("CONSUMER_METRICS_PORT", "9101"))
MAX_PROCESSING_ATTEMPTS = 3
REDIS_TTL_SECONDS = 3600

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("fraud-scorer")

transactions_total = Counter(
    "fraudradar_transactions_total",
    "Total transactions scored by risk level.",
    ["risk_level"],
)
fraud_detected_total = Counter(
    "fraudradar_fraud_detected_total",
    "Total transactions scored as fraud.",
)
scoring_latency_seconds = Histogram(
    "fraudradar_scoring_latency_seconds",
    "Transaction scoring latency in seconds.",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

running = True


def request_shutdown(signum: int, _frame: Any) -> None:
    global running
    logger.info("Received signal %s. Stopping scorer after current poll.", signum)
    running = False


def configure_model_paths() -> None:
    model_dir = Path(os.getenv("MODEL_DIR", "models"))
    score_utils.MODEL_DIR = model_dir
    score_utils.ISOLATION_FOREST_PATH = model_dir / "isolation_forest.joblib"
    score_utils.SCALER_PATH = model_dir / "scaler.joblib"

    keras_path = model_dir / "autoencoder.keras"
    h5_path = model_dir / "autoencoder.h5"
    score_utils.AUTOENCODER_PATH = keras_path if keras_path.exists() else h5_path

    thresholds_path = model_dir / "thresholds.json"
    threshold_path = model_dir / "threshold.json"
    score_utils.THRESHOLD_PATH = thresholds_path if thresholds_path.exists() else threshold_path


def kafka_servers() -> list[str]:
    return [server.strip() for server in KAFKA_BOOTSTRAP_SERVERS.split(",") if server.strip()]


def deserialize_transaction(raw_value: bytes | bytearray | memoryview) -> dict[str, Any]:
    transaction = json.loads(bytes(raw_value).decode("utf-8"))
    if not isinstance(transaction, dict):
        raise ValueError("Kafka message value must be a JSON object")
    if not transaction.get("transaction_id"):
        raise ValueError("Transaction is missing transaction_id")
    return transaction


def json_serializer(value: dict[str, Any]) -> bytes:
    return json.dumps(value, separators=(",", ":"), default=str).encode("utf-8")


def make_consumer() -> KafkaConsumer:
    delay_seconds = 1.0
    attempt = 1
    while running:
        try:
            consumer = KafkaConsumer(
                TRANSACTIONS_TOPIC,
                bootstrap_servers=kafka_servers(),
                group_id=CONSUMER_GROUP,
                enable_auto_commit=False,
                auto_offset_reset="earliest",
                max_poll_records=25,
                consumer_timeout_ms=1000,
                key_deserializer=lambda value: value.decode("utf-8") if value else None,
                value_deserializer=None,
                api_version_auto_timeout_ms=10000,
            )
            logger.info(
                "Subscribed to Kafka topic '%s' with consumer group '%s'",
                TRANSACTIONS_TOPIC,
                CONSUMER_GROUP,
            )
            return consumer
        except NoBrokersAvailable as exc:
            logger.warning(
                "Kafka is not ready for consumer connection (attempt %s). Retrying in %.1fs: %s",
                attempt,
                delay_seconds,
                exc,
            )
            time.sleep(delay_seconds)
            delay_seconds = min(delay_seconds * 2, 30.0)
            attempt += 1
    raise RuntimeError("Shutdown requested before Kafka consumer was created")


def make_producer() -> KafkaProducer:
    delay_seconds = 1.0
    attempt = 1
    while running:
        try:
            producer = KafkaProducer(
                bootstrap_servers=kafka_servers(),
                value_serializer=json_serializer,
                key_serializer=lambda value: value.encode("utf-8"),
                acks="all",
                retries=10,
                linger_ms=10,
                request_timeout_ms=30000,
                api_version_auto_timeout_ms=10000,
            )
            logger.info("Connected Kafka producer to %s", ",".join(kafka_servers()))
            return producer
        except NoBrokersAvailable as exc:
            logger.warning(
                "Kafka is not ready for producer connection (attempt %s). Retrying in %.1fs: %s",
                attempt,
                delay_seconds,
                exc,
            )
            time.sleep(delay_seconds)
            delay_seconds = min(delay_seconds * 2, 30.0)
            attempt += 1
    raise RuntimeError("Shutdown requested before Kafka producer was created")


def publish_score(producer: KafkaProducer, result: dict[str, Any]) -> None:
    future = producer.send(
        FRAUD_SCORES_TOPIC,
        key=str(result["transaction_id"]),
        value=result,
    )
    future.get(timeout=30)
    producer.flush(timeout=10)


def cache_score(cache: redis.Redis, result: dict[str, Any]) -> None:
    cache.setex(
        f"tx:{result['transaction_id']}",
        REDIS_TTL_SECONDS,
        json.dumps(result, separators=(",", ":"), default=str),
    )


def build_result_payload(transaction: dict[str, Any]) -> tuple[dict[str, Any], float]:
    started_at = time.perf_counter()
    fraud_scores = score_utils.score_transaction(transaction)
    latency = time.perf_counter() - started_at

    return {
        **transaction,
        **fraud_scores,
        "scored_at": datetime.now(tz=timezone.utc).isoformat(),
    }, latency


def update_metrics(result: dict[str, Any], latency_seconds: float) -> None:
    risk_level = str(result.get("risk_level", "UNKNOWN"))
    transactions_total.labels(risk_level=risk_level).inc()
    if bool(result.get("is_fraud")):
        fraud_detected_total.inc()
    scoring_latency_seconds.observe(latency_seconds)


def process_message(
    raw_value: bytes,
    producer: KafkaProducer,
    cache: redis.Redis,
) -> dict[str, Any]:
    transaction = deserialize_transaction(raw_value)
    result, latency_seconds = build_result_payload(transaction)

    publish_score(producer, result)
    upsert_transaction(result)
    cache_score(cache, result)
    update_metrics(result, latency_seconds)

    logger.info(
        "Scored transaction_id=%s risk_level=%s probability=%.6f is_fraud=%s",
        result["transaction_id"],
        result.get("risk_level"),
        float(result.get("combined_fraud_probability", 0.0)),
        result.get("is_fraud"),
    )
    return result


def handle_failed_message(raw_value: bytes, error: Exception) -> None:
    try:
        transaction = deserialize_transaction(raw_value)
    except Exception:
        transaction = {"raw_message": raw_value.decode("utf-8", errors="replace")}
    write_failed(transaction, str(error))


def process_with_dead_letter(
    raw_value: bytes,
    producer: KafkaProducer,
    cache: redis.Redis,
) -> bool:
    last_error: Exception | None = None
    for attempt in range(1, MAX_PROCESSING_ATTEMPTS + 1):
        try:
            process_message(raw_value, producer, cache)
            return True
        except Exception as exc:
            last_error = exc
            logger.exception(
                "Failed to score transaction attempt %s/%s",
                attempt,
                MAX_PROCESSING_ATTEMPTS,
            )
            if attempt < MAX_PROCESSING_ATTEMPTS:
                time.sleep(min(2**attempt, 10))

    assert last_error is not None
    try:
        handle_failed_message(raw_value, last_error)
        logger.error("Moved failed transaction to failed_transactions: %s", last_error)
        return True
    except Exception:
        logger.exception("Failed to write message to failed_transactions")
        return False


def main() -> None:
    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)

    start_http_server(METRICS_PORT)
    configure_model_paths()
    init_db()

    cache = redis.from_url(REDIS_URL, decode_responses=True)
    consumer = make_consumer()
    producer = make_producer()

    logger.info(
        "Fraud scorer started. Input topic='%s', output topic='%s', metrics_port=%s",
        TRANSACTIONS_TOPIC,
        FRAUD_SCORES_TOPIC,
        METRICS_PORT,
    )

    try:
        while running:
            records = consumer.poll(timeout_ms=1000, max_records=25)
            for messages in records.values():
                for message in messages:
                    if not running:
                        break
                    should_commit = process_with_dead_letter(message.value, producer, cache)
                    if should_commit:
                        consumer.commit()
    except KafkaError:
        logger.exception("Kafka error in scoring loop")
        raise
    finally:
        logger.info("Closing scorer resources")
        try:
            consumer.close()
        finally:
            producer.flush(timeout=10)
            producer.close(timeout=10)
            cache.close()


if __name__ == "__main__":
    main()

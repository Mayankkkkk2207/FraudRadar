from __future__ import annotations

import json
import logging
import os
import random
import signal
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from faker import Faker
from kafka import KafkaProducer
from kafka.errors import KafkaError, NoBrokersAvailable

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", os.getenv("TRANSACTIONS_TOPIC", "transactions"))
TRANSACTION_RATE_PER_SECOND = float(
    os.getenv("TRANSACTION_RATE_PER_SECOND", os.getenv("PRODUCER_RATE_PER_SECOND", "2"))
)
SUSPICIOUS_INTERVAL = int(os.getenv("SUSPICIOUS_INTERVAL", "50"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))

MERCHANT_CATEGORIES = [
    "groceries",
    "electronics",
    "restaurant",
    "travel",
    "online_retail",
    "gas_station",
    "pharmacy",
    "entertainment",
]
CARD_TYPES = ["Visa", "MC", "Amex", "Discover"]
DEVICE_TYPES = ["mobile", "web", "pos"]
US_CITY_COUNTRY = [
    ("New York", "United States"),
    ("Los Angeles", "United States"),
    ("Chicago", "United States"),
    ("Houston", "United States"),
    ("Phoenix", "United States"),
    ("Philadelphia", "United States"),
    ("San Antonio", "United States"),
    ("San Diego", "United States"),
    ("Dallas", "United States"),
    ("San Jose", "United States"),
]
INTERNATIONAL_CITY_COUNTRY = [
    ("London", "United Kingdom"),
    ("Toronto", "Canada"),
    ("Mexico City", "Mexico"),
    ("Paris", "France"),
    ("Berlin", "Germany"),
    ("Tokyo", "Japan"),
    ("Sao Paulo", "Brazil"),
    ("Singapore", "Singapore"),
    ("Dubai", "United Arab Emirates"),
    ("Lagos", "Nigeria"),
]

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("transaction-simulator")

fake = Faker("en_US")
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)
running = True


def request_shutdown(signum: int, _frame: Any) -> None:
    global running
    logger.info("Received signal %s. Stopping producer gracefully.", signum)
    running = False


def json_serializer(value: dict[str, Any]) -> bytes:
    return json.dumps(value, separators=(",", ":"), default=str).encode("utf-8")


def create_producer() -> KafkaProducer:
    servers = [server.strip() for server in KAFKA_BOOTSTRAP_SERVERS.split(",") if server.strip()]
    delay_seconds = 1.0
    max_delay_seconds = 30.0
    attempt = 1

    while running:
        try:
            producer = KafkaProducer(
                bootstrap_servers=servers,
                value_serializer=json_serializer,
                key_serializer=lambda value: value.encode("utf-8"),
                acks="all",
                retries=5,
                linger_ms=10,
                request_timeout_ms=30000,
                api_version_auto_timeout_ms=10000,
            )
            logger.info("Connected to Kafka at %s", ",".join(servers))
            return producer
        except NoBrokersAvailable as exc:
            logger.warning(
                "Kafka is not ready yet (attempt %s). Retrying in %.1fs. Error: %s",
                attempt,
                delay_seconds,
                exc,
            )
            time.sleep(delay_seconds)
            delay_seconds = min(delay_seconds * 2, max_delay_seconds)
            attempt += 1

    raise RuntimeError("Shutdown requested before Kafka connection was established.")


def realistic_amount(category: str, suspicious: bool) -> float:
    if suspicious:
        return round(random.uniform(5000.0, 25000.0), 2)

    category_ranges = {
        "groceries": (8.0, 180.0),
        "electronics": (20.0, 900.0),
        "restaurant": (7.0, 220.0),
        "travel": (45.0, 1800.0),
        "online_retail": (5.0, 500.0),
        "gas_station": (15.0, 140.0),
        "pharmacy": (5.0, 250.0),
        "entertainment": (10.0, 350.0),
    }

    low, high = category_ranges[category]
    if random.random() < 0.9:
        amount = random.lognormvariate(3.2, 0.65)
        return round(max(low, min(amount, high * 0.45)), 2)

    return round(random.uniform(high * 0.45, high), 2)


def transaction_timestamp(suspicious: bool) -> str:
    now = datetime.now(timezone.utc)
    if not suspicious:
        seconds_back = random.randint(0, 600)
        return (now - timedelta(seconds=seconds_back)).isoformat()

    odd_hour = random.choice([0, 1, 2, 3, 4])
    odd_minute = random.randint(0, 59)
    odd_second = random.randint(0, 59)
    return now.replace(hour=odd_hour, minute=odd_minute, second=odd_second, microsecond=0).isoformat()


def generate_transaction(sequence_number: int = 1, force_suspicious: bool = False) -> dict[str, Any]:
    suspicious = force_suspicious or (
        SUSPICIOUS_INTERVAL > 0 and sequence_number % SUSPICIOUS_INTERVAL == 0
    )
    merchant_category = "travel" if suspicious else random.choice(MERCHANT_CATEGORIES)
    city, country = (
        random.choice(INTERNATIONAL_CITY_COUNTRY)
        if suspicious or random.random() < 0.08
        else random.choice(US_CITY_COUNTRY)
    )

    return {
        "transaction_id": str(uuid.uuid4()),
        "user_id": f"user_{random.randint(100000, 999999)}",
        "merchant_id": f"merchant_{random.randint(10000, 99999)}",
        "merchant_name": fake.company(),
        "merchant_category": merchant_category,
        "amount": realistic_amount(merchant_category, suspicious),
        "currency": "USD",
        "location": {"city": city, "country": country},
        "timestamp": transaction_timestamp(suspicious),
        "card_last_four": f"{random.randint(0, 9999):04d}",
        "card_type": random.choice(CARD_TYPES),
        "is_international": country != "United States",
        "device_type": random.choice(["mobile", "web"] if suspicious else DEVICE_TYPES),
    }


def truncate_json(transaction: dict[str, Any], limit: int = 240) -> str:
    payload = json.dumps(transaction, separators=(",", ":"))
    return payload if len(payload) <= limit else f"{payload[: limit - 3]}..."


def send_transaction(
    producer: KafkaProducer,
    transaction: dict[str, Any],
    max_attempts: int = 5,
) -> KafkaProducer:
    delay_seconds = 1.0

    for attempt in range(1, max_attempts + 1):
        try:
            future = producer.send(
                KAFKA_TOPIC,
                key=transaction["transaction_id"],
                value=transaction,
            )
            future.get(timeout=15)
            logger.info("Produced transaction: %s", truncate_json(transaction))
            return producer
        except KafkaError as exc:
            logger.warning(
                "Failed to send transaction %s (attempt %s/%s): %s",
                transaction["transaction_id"],
                attempt,
                max_attempts,
                exc,
            )
            try:
                producer.close(timeout=5)
            except KafkaError:
                pass

            if attempt == max_attempts or not running:
                raise

            time.sleep(delay_seconds)
            delay_seconds *= 2
            producer = create_producer()

    return producer


def main() -> None:
    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)

    producer = create_producer()
    sleep_seconds = 1 / TRANSACTION_RATE_PER_SECOND if TRANSACTION_RATE_PER_SECOND > 0 else 0
    sequence_number = 1

    logger.info(
        "Producing transactions to topic '%s' at %.2f/sec",
        KAFKA_TOPIC,
        TRANSACTION_RATE_PER_SECOND,
    )

    try:
        while running:
            transaction = generate_transaction(sequence_number=sequence_number)
            producer = send_transaction(producer, transaction)
            sequence_number += 1

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
    finally:
        logger.info("Flushing and closing Kafka producer.")
        producer.flush(timeout=10)
        producer.close(timeout=10)
        logger.info("Producer stopped.")


if __name__ == "__main__":
    main()

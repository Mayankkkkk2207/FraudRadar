from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

from kafka import KafkaConsumer, KafkaProducer, TopicPartition
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import (
    KafkaError,
    NoBrokersAvailable,
    TopicAlreadyExistsError,
    UnknownTopicOrPartitionError,
)

from simulator import generate_transaction, json_serializer

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", os.getenv("TRANSACTIONS_TOPIC", "transactions"))
TEST_TRANSACTION_COUNT = int(os.getenv("TEST_TRANSACTION_COUNT", "10"))
TEST_TIMEOUT_SECONDS = int(os.getenv("TEST_TIMEOUT_SECONDS", "30"))


def bootstrap_servers() -> list[str]:
    return [server.strip() for server in KAFKA_BOOTSTRAP_SERVERS.split(",") if server.strip()]


def create_admin_client(max_attempts: int = 8) -> KafkaAdminClient:
    delay_seconds = 1.0
    for attempt in range(1, max_attempts + 1):
        try:
            return KafkaAdminClient(
                bootstrap_servers=bootstrap_servers(),
                client_id=f"producer-test-admin-{uuid.uuid4()}",
                request_timeout_ms=5000,
                api_version_auto_timeout_ms=5000,
            )
        except NoBrokersAvailable as exc:
            print(
                f"Kafka not ready for admin client (attempt {attempt}/{max_attempts}): {exc}"
            )
            time.sleep(delay_seconds)
            delay_seconds = min(delay_seconds * 2, 10)
    raise RuntimeError("Could not connect Kafka admin client.")


def ensure_topic_exists() -> None:
    admin = create_admin_client()
    try:
        admin.create_topics(
            [NewTopic(name=KAFKA_TOPIC, num_partitions=1, replication_factor=1)],
            validate_only=False,
        )
        print(f"Created Kafka topic '{KAFKA_TOPIC}'.")
    except TopicAlreadyExistsError:
        print(f"Kafka topic '{KAFKA_TOPIC}' already exists.")
    finally:
        admin.close()


def create_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=bootstrap_servers(),
        value_serializer=json_serializer,
        key_serializer=lambda value: value.encode("utf-8"),
        acks="all",
        request_timeout_ms=30000,
        api_version_auto_timeout_ms=10000,
    )


def create_consumer() -> KafkaConsumer:
    return KafkaConsumer(
        bootstrap_servers=bootstrap_servers(),
        client_id=f"producer-test-consumer-{uuid.uuid4()}",
        group_id=f"producer-test-{uuid.uuid4()}",
        auto_offset_reset="latest",
        enable_auto_commit=False,
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        request_timeout_ms=30000,
        api_version_auto_timeout_ms=10000,
    )


def wait_for_topic_partitions(consumer: KafkaConsumer, timeout_seconds: int = 20) -> list[TopicPartition]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        partitions = consumer.partitions_for_topic(KAFKA_TOPIC)
        if partitions:
            return [TopicPartition(KAFKA_TOPIC, partition) for partition in partitions]
        time.sleep(1)
    raise UnknownTopicOrPartitionError(f"No partitions found for topic '{KAFKA_TOPIC}'.")


def send_test_transactions(producer: KafkaProducer) -> list[dict[str, Any]]:
    transactions = [
        generate_transaction(sequence_number=sequence_number)
        for sequence_number in range(1, TEST_TRANSACTION_COUNT + 1)
    ]

    for transaction in transactions:
        future = producer.send(
            KAFKA_TOPIC,
            key=transaction["transaction_id"],
            value=transaction,
        )
        future.get(timeout=15)
        print(f"SENT    {transaction['transaction_id']}")

    producer.flush(timeout=10)
    return transactions


def verify_transactions(
    consumer: KafkaConsumer,
    transactions: list[dict[str, Any]],
) -> dict[str, bool]:
    expected_ids = {transaction["transaction_id"] for transaction in transactions}
    seen = dict.fromkeys(expected_ids, False)
    deadline = time.monotonic() + TEST_TIMEOUT_SECONDS

    while time.monotonic() < deadline and not all(seen.values()):
        records = consumer.poll(timeout_ms=1000, max_records=100)
        for batch in records.values():
            for record in batch:
                transaction_id = record.value.get("transaction_id")
                if transaction_id in seen:
                    seen[transaction_id] = True

    return seen


def main() -> None:
    ensure_topic_exists()

    producer = create_producer()
    consumer = create_consumer()

    try:
        topic_partitions = wait_for_topic_partitions(consumer)
        consumer.assign(topic_partitions)
        consumer.seek_to_end(*topic_partitions)

        transactions = send_test_transactions(producer)
        results = verify_transactions(consumer, transactions)

        failed = False
        for transaction in transactions:
            transaction_id = transaction["transaction_id"]
            if results[transaction_id]:
                print(f"SUCCESS {transaction_id} appeared in Kafka.")
            else:
                print(f"FAILURE {transaction_id} did not appear in Kafka.")
                failed = True

        raise SystemExit(1 if failed else 0)
    except KafkaError as exc:
        print(f"FAILURE Kafka test failed: {exc}")
        raise SystemExit(1) from exc
    finally:
        producer.close(timeout=10)
        consumer.close()


if __name__ == "__main__":
    main()

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    MODEL_DIR=/app/models

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY training ./training
COPY models ./models
COPY consumer ./consumer

RUN printf '%s\n' \
    '#!/bin/sh' \
    'set -e' \
    '' \
    'python - <<'"'"'PY'"'"'' \
    'import os' \
    'import time' \
    'from kafka import KafkaProducer' \
    'from kafka.errors import NoBrokersAvailable' \
    '' \
    'servers = [server.strip() for server in os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092").split(",") if server.strip()]' \
    'last_error = None' \
    'for attempt in range(1, 61):' \
    '    try:' \
    '        producer = KafkaProducer(bootstrap_servers=servers, request_timeout_ms=5000, api_version_auto_timeout_ms=5000)' \
    '        producer.close(timeout=5)' \
    '        print(f"Kafka is ready at {servers}")' \
    '        break' \
    '    except NoBrokersAvailable as exc:' \
    '        last_error = exc' \
    '        print(f"Waiting for Kafka ({attempt}/60): {exc}", flush=True)' \
    '        time.sleep(2)' \
    'else:' \
    '    raise SystemExit(f"Kafka was not ready: {last_error}")' \
    'PY' \
    '' \
    'python - <<'"'"'PY'"'"'' \
    'import os' \
    'import time' \
    'from sqlalchemy import create_engine, text' \
    '' \
    'url = os.getenv("DATABASE_URL", "postgresql+psycopg2://fraudradar:fraudradar@localhost:5432/fraudradar")' \
    'engine = create_engine(url, pool_pre_ping=True, future=True)' \
    'last_error = None' \
    'for attempt in range(1, 61):' \
    '    try:' \
    '        with engine.connect() as connection:' \
    '            connection.execute(text("SELECT 1"))' \
    '        print("PostgreSQL is ready")' \
    '        break' \
    '    except Exception as exc:' \
    '        last_error = exc' \
    '        print(f"Waiting for PostgreSQL ({attempt}/60): {exc}", flush=True)' \
    '        time.sleep(2)' \
    'else:' \
    '    raise SystemExit(f"PostgreSQL was not ready: {last_error}")' \
    'PY' \
    '' \
    'cd /app/consumer' \
    'exec "$@"' \
    > /usr/local/bin/fraud-scorer-entrypoint \
    && chmod +x /usr/local/bin/fraud-scorer-entrypoint

EXPOSE 9101

ENTRYPOINT ["fraud-scorer-entrypoint"]
CMD ["python", "scorer.py"]

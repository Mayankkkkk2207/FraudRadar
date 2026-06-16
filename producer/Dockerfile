FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY producer ./producer

WORKDIR /app/producer

CMD ["sh", "-c", "python - <<'PY'\nimport os\nimport time\nfrom kafka import KafkaProducer\nfrom kafka.errors import KafkaError, NoBrokersAvailable\n\nservers = [server.strip() for server in os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092').split(',') if server.strip()]\ndelay = 1\nattempt = 1\nwhile True:\n    try:\n        producer = KafkaProducer(bootstrap_servers=servers, request_timeout_ms=5000, api_version_auto_timeout_ms=5000)\n        producer.bootstrap_connected()\n        producer.close()\n        print(f'Kafka is ready at {servers}', flush=True)\n        break\n    except (KafkaError, NoBrokersAvailable) as exc:\n        print(f'Waiting for Kafka at {servers} (attempt {attempt}): {exc}', flush=True)\n        time.sleep(delay)\n        delay = min(delay * 2, 30)\n        attempt += 1\nPY\nexec python simulator.py"]

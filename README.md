# FraudRadar

FraudRadar is a real-time fraud detection system built with Python, FastAPI, Kafka, PostgreSQL, Redis, Prometheus, Grafana, and machine learning models. It simulates payment transactions, streams them through Kafka, scores them for fraud risk, stores the results, and exposes APIs and dashboards for monitoring.

## Day-Wise Work Completed

### Day 1 - Project Setup and Core ML Foundation

- Created the base project structure for the FraudRadar system.
- Added the main Python packages and folders:
  - `api/` for the FastAPI backend.
  - `producer/` for transaction simulation.
  - `consumer/` for Kafka-based fraud scoring.
  - `fraudradar/` for shared settings, feature processing, and scoring logic.
  - `training/` for model training scripts.
  - `models/` for saved ML artifacts.
  - `data/` for the credit card fraud dataset.
  - `tests/` for API tests.
- Added configuration through `.env` for Kafka, PostgreSQL, Redis, model paths, service ports, thresholds, and Grafana credentials.
- Added `requirements.txt` with the Python dependencies needed by the API, producer, consumer, training scripts, database, metrics, and tests.
- Added feature engineering utilities to normalize transaction payloads into the model feature format.
- Implemented fraud scoring with:
  - Isolation Forest anomaly detection.
  - Autoencoder reconstruction-error detection.
  - Rules-based fraud heuristics for high amount, risky country, risky category, and missing device ID.
- Added automatic bootstrap model creation so the app can still run if trained model files are missing.
- Added model artifacts in `models/`, including:
  - `isolation_forest.joblib`
  - `scaler.joblib`
  - `autoencoder.keras`
  - `thresholds.json`
- Added training scripts for real dataset workflows:
  - `training/train_isolation_forest.py`
  - `training/train_autoencoder.py`
  - `training/score_utils.py`
- Added support for the Kaggle credit card fraud dataset at `data/creditcard.csv`.

### Day 2 - Streaming Pipeline, API, Database, and Monitoring

- Built the Docker-based local infrastructure in `docker-compose.yml`.
- Added services for:
  - Zookeeper
  - Kafka
  - Kafka topic initialization
  - PostgreSQL
  - Redis
  - FastAPI backend
  - Producer simulator
  - Consumer scorer
  - Prometheus
  - Grafana
- Added health checks for the major services so Docker can wait for dependencies before starting app services.
- Created Kafka topics for:
  - `transactions`
  - `fraud_scores`
- Built the transaction producer in `producer/simulator.py`.
- Added realistic transaction generation with:
  - Merchant categories.
  - Random card, user, merchant, location, amount, and timestamp fields.
  - Periodic suspicious transactions.
  - Kafka retry and graceful shutdown behavior.
- Built the Kafka consumer and scorer in `consumer/scorer.py`.
- Added consumer behavior for:
  - Reading raw transactions from Kafka.
  - Scoring transactions with ML and rules.
  - Publishing scored results back to Kafka.
  - Writing scores to PostgreSQL.
  - Caching recent scores in Redis.
  - Exposing Prometheus metrics on port `9101`.
  - Retrying failed messages and writing persistent failures.
- Added database writing helpers in `consumer/db_writer.py`.
- Added SQLAlchemy database models in `api/models_db.py`.
- Added Alembic migration support with the initial migration at `alembic/versions/202606160001_initial_schema.py`.
- Built the FastAPI application in `api/main.py`.
- Added API startup logic for:
  - Database initialization.
  - ML model artifact checks.
  - Request logging.
  - Prometheus metrics exposure.
  - Router registration.
- Added transaction APIs in `api/routes/transactions.py`:
  - `POST /transactions/score`
  - `GET /transactions`
  - `GET /transactions/{transaction_id}`
  - `WS /transactions/live`
- Added stats and health APIs in `api/routes/stats.py`:
  - `GET /stats`
  - `GET /health`
- Added API schemas in `api/schemas.py` for request validation and structured responses.
- Added Prometheus configuration in `monitoring/prometheus.yml`.
- Added Grafana provisioning files and dashboard JSON under `monitoring/grafana/`.
- Added startup automation in `scripts/run_all.sh`.
- Added Dockerfiles for the API, producer, and consumer services.
- Added API tests in `tests/test_api.py` covering:
  - Health checks.
  - Transaction scoring.
  - Pagination.
  - Transaction lookup.
  - Stats.
  - Risk-level filtering.
  - End-to-end API workflow.
- Added `.dockerignore` and setup scripts for cleaner local development.

## Final Architecture

```text
Producer Simulator
      |
      v
Kafka topic: transactions
      |
      v
Consumer Scorer
      |
      +--> ML scoring: Isolation Forest + Autoencoder + heuristics
      +--> Kafka topic: fraud_scores
      +--> PostgreSQL: transaction_scores
      +--> Redis: recent score cache
      +--> Prometheus metrics

FastAPI
      |
      +--> Score a transaction on demand
      +--> List and filter scored transactions
      +--> Return fraud statistics
      +--> Stream live transactions over WebSocket
      +--> Expose health and metrics endpoints

Prometheus + Grafana
      |
      +--> Monitor API, consumer, transaction, fraud, and latency metrics
```

## Main Features

- Real-time transaction simulation.
- Kafka event streaming.
- Fraud risk scoring using ML and business rules.
- PostgreSQL persistence.
- Redis caching.
- FastAPI REST API and WebSocket endpoint.
- Prometheus metrics.
- Grafana dashboard provisioning.
- Docker Compose setup for the full local stack.
- Alembic migration support.
- API test suite.
- Optional model training from the Kaggle credit card fraud dataset.

## Project Structure

```text
fraud_radar/
  api/                  FastAPI app, routes, schemas, database models
  consumer/             Kafka consumer, scorer, database writer
  producer/             Kafka transaction simulator
  fraudradar/           Shared settings, features, scoring logic
  training/             Model training and scoring utilities
  models/               Trained or bootstrap model artifacts
  data/                 Dataset location
  monitoring/           Prometheus and Grafana configuration
  alembic/              Database migrations
  scripts/              Startup scripts
  tests/                API tests
  docker-compose.yml    Complete service orchestration
  requirements.txt      Python dependencies
  .env                  Local environment configuration
```

## Prerequisites

- **Docker & Docker Compose** - [Install](https://docs.docker.com/get-docker/)
- **Git** - [Install](https://git-scm.com/)
- **Bash** - Git Bash (Windows), WSL, Linux, or macOS Terminal
- **4GB+ RAM** - Minimum for comfortable development
- **Python 3.10+** (optional, for local testing)

## Quick Start (5 Commands)

```bash
# 1. Clone and navigate
git clone <repo-url> fraud_radar && cd fraud_radar

# 2. Configure environment (optional - defaults provided)
cat .env

# 3. Start the complete system
bash scripts/run_all.sh

# 4. Wait for health checks (auto-handled by script)
curl http://localhost:8000/health

# 5. Access services
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
# Grafana: http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9090
```

## Complete Setup Guide

### Step 1: Clone Repository

```bash
git clone <your-repo-url> fraud_radar
cd fraud_radar
```

### Step 2: Review Environment Configuration

```bash
cat .env
```

Key variables (with defaults):
```env
# Database
POSTGRES_USER=fraudradar
POSTGRES_PASSWORD=fraudradar
POSTGRES_DB=fraudradar

# Grafana
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin

# Kafka (defaults usually work)
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
KAFKA_RAW_TOPIC=transactions
KAFKA_SCORED_TOPIC=fraud_scores
```

### Step 3: Build Services

```bash
docker-compose build
```

### Step 4: Start the System

```bash
bash scripts/run_all.sh
```

This script:
1. Cleans up existing containers/volumes
2. Starts infrastructure (Kafka, Postgres, Redis)
3. Waits for services to stabilize (30 seconds)
4. Initializes Kafka topics
5. Starts API, Producer, Consumer, Prometheus, Grafana
6. Waits for application health checks
7. Prints service URLs

### Step 5: Verify All Services

```bash
# Check container status
docker-compose ps

# Check API health
curl http://localhost:8000/health

# Check Kafka topics
docker-compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FraudRadar System                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐        ┌──────────────┐       ┌──────────────┐  │
│  │  Producer    │──────>│   Kafka      │──────>│  Consumer    │  │
│  │  Simulator   │        │  Broker      │       │  Scorer      │  │
│  └──────────────┘        └──────────────┘       └──────────────┘  │
│       (8 TPS)              (Topics)               (Scoring ML)     │
│                                                        │            │
│                                                        ├───> PostgreSQL
│                                                        ├───> Redis
│                                                        └───> Prometheus
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                      FastAPI Application                     │  │
│  │                       (http://8000)                          │  │
│  │  ┌──────────────────────────────────────────────────────┐  │
│  │  │ Endpoints:                                            │  │
│  │  │ • POST   /transactions/score     - Score transaction  │  │
│  │  │ • GET    /transactions            - List (paginated)  │  │
│  │  │ • GET    /transactions/{id}       - Get by ID         │  │
│  │  │ • GET    /stats                   - Statistics        │  │
│  │  │ • GET    /health                  - Health check      │  │
│  │  │ • GET    /metrics                 - Prometheus        │  │
│  │  └──────────────────────────────────────────────────────┘  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                  Monitoring & Analytics                     │  │
│  │  • Prometheus  (http://9090)  - Metrics collection         │  │
│  │  • Grafana     (http://3000)  - Dashboard & visualization  │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Infrastructure:                                                    │
│  • PostgreSQL 15      - Transaction storage & audit trail         │
│  • Redis 7           - Session cache & real-time data             │
│  • Zookeeper         - Kafka coordination                         │
└─────────────────────────────────────────────────────────────────────┘
```

## Components

| Service | Purpose | Port | Health Check |
|---------|---------|------|--------------|
| **Zookeeper** | Kafka coordination | 2181 | srvr command |
| **Kafka** | Event streaming | 9092 | broker-api-versions |
| **PostgreSQL** | Transaction database | 5432 | pg_isready |
| **Redis** | Cache layer | 6379 | PING |
| **API** | FastAPI application | 8000 | /health endpoint |
| **Producer** | Transaction simulator | - | Kafka connectivity |
| **Consumer** | ML scoring service | 9101 | /metrics endpoint |
| **Prometheus** | Metrics collection | 9090 | /-/healthy |
| **Grafana** | Dashboards & alerts | 3000 | /api/health |

## API Endpoint Reference

### Health & Stats

| Method | Endpoint | Description | Returns |
|--------|----------|-------------|---------|
| GET | `/health` | System health check | `{status: "ok\|degraded\|error", ...}` |
| GET | `/stats` | Fraud statistics | Counts, rates, breakdowns |
| GET | `/docs` | Interactive API docs | Swagger UI |
| GET | `/redoc` | Alternative API docs | ReDoc |

### Transaction Scoring

| Method | Endpoint | Description | Body |
|--------|----------|-------------|------|
| POST | `/transactions/score` | Score transaction (on-demand) | Transaction JSON |
| GET | `/transactions` | List transactions (paginated) | Query params: page, limit, risk_level, is_fraud |
| GET | `/transactions/{id}` | Get transaction by ID | - |
| WS | `/transactions/live` | WebSocket: live transactions | - |

### Request/Response Examples

**Score a Transaction:**
```bash
curl -X POST http://localhost:8000/transactions/score \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 100.00,
    "currency": "USD",
    "merchant": "Amazon",
    "category": "shopping",
    "card_id": "card_123",
    "customer_id": "cus_456",
    "country": "US",
    "ip_address": "192.168.1.1",
    "device_id": "device_789"
  }'
```

**List Transactions (Paginated):**
```bash
curl "http://localhost:8000/transactions?page=1&limit=50&risk_level=high"
```

**Get Statistics:**
```bash
curl http://localhost:8000/stats
```

**Response Example (Stats):**
```json
{
  "total_transactions": 1523,
  "fraud_detected": 47,
  "fraud_rate_percent": 3.09,
  "avg_fraud_probability": 0.38,
  "risk_breakdown": {
    "LOW": 1200,
    "MEDIUM": 250,
    "HIGH": 70,
    "CRITICAL": 3
  },
  "top_fraud_merchants": [
    {"merchant_name": "Online Casino", "count": 15},
    {"merchant_name": "Foreign ATM", "count": 12}
  ],
  "transactions_last_hour": 156,
  "fraud_last_hour": 4
}
```

## Grafana Dashboard

### Access

- **URL:** http://localhost:3000
- **Default Credentials:** admin / admin
- **Dashboard Name:** FraudRadar Dashboard

### Panels

The FraudRadar Dashboard includes 6 key monitoring panels:

1. **Fraud Detected (Total)** - Stat panel showing total frauds in the last hour
2. **Fraud Rate %** - Gauge showing fraud percentage with color thresholds
3. **Risk Level Breakdown** - Pie chart of transactions by risk level
4. **Scoring Latency p50/p95/p99** - Time series of scoring performance
5. **Transactions Per Minute** - Line chart of transaction throughput
6. **Top Fraud Merchant Categories** - Bar chart of merchants with most fraud

### Creating Custom Dashboards

1. Click **+** > **Dashboard**
2. Click **Add panel**
3. Select **Prometheus** as datasource
4. Use queries like:
   ```
   sum(rate(fraudradar_fraud_detected_total[1h]))
   histogram_quantile(0.95, fraudradar_scoring_latency_seconds_bucket)
   ```
5. Save and share

## Running Tests

### Prerequisites for Testing

Install test dependencies:
```bash
pip install pytest pytest-asyncio httpx
```

### Run All Tests

```bash
pytest tests/ -v
```

### Run Specific Test Classes

```bash
# Health check tests
pytest tests/test_api.py::TestHealthCheck -v

# Transaction scoring tests
pytest tests/test_api.py::TestTransactionScoring -v

# Pagination tests
pytest tests/test_api.py::TestTransactionsList -v

# Stats endpoint tests
pytest tests/test_api.py::TestStats -v

# Risk level filtering tests
pytest tests/test_api.py::TestRiskLevelFiltering -v

# Integration tests
pytest tests/test_api.py::TestAPIIntegration -v
```

### Run with Coverage

```bash
pip install pytest-cov
pytest tests/ --cov=api --cov-report=html
```

### Expected Test Output

```
tests/test_api.py::TestHealthCheck::test_health_check PASSED
tests/test_api.py::TestTransactionScoring::test_score_transaction PASSED
tests/test_api.py::TestTransactionsList::test_get_transactions_paginated PASSED
tests/test_api.py::TestTransactionById::test_get_transaction_by_id PASSED
tests/test_api.py::TestStats::test_get_stats PASSED
tests/test_api.py::TestRiskLevelFiltering::test_filter_by_risk_level_low PASSED
tests/test_api.py::TestRiskLevelFiltering::test_filter_by_risk_level_high PASSED
tests/test_api.py::TestAPIIntegration::test_full_workflow PASSED

======================== 30 passed in 12.45s ========================
```

## Kaggle Dataset (Optional)

FraudRadar uses the Kaggle "Credit Card Fraud Detection" dataset when available at:

```text
data/creditcard.csv
```

To enable automatic download:

```bash
pip install kaggle
mkdir -p ~/.kaggle
```

Create a Kaggle API token from [https://www.kaggle.com/settings](https://www.kaggle.com/settings), place it at `~/.kaggle/kaggle.json`, then run:

```bash
chmod 600 ~/.kaggle/kaggle.json
bash setup.sh
```

Manual fallback:

1. Download the dataset from [https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud).
2. Extract `creditcard.csv`.
3. Place it at `data/creditcard.csv`.

The stack can still start without this file. If trained model artifacts are absent, the API bootstraps local model artifacts so the service is usable immediately.

### Train Models

After `data/creditcard.csv` exists, train both models:

```bash
python -m training.train_isolation_forest --dataset data/creditcard.csv --model-dir models
python -m training.train_autoencoder --dataset data/creditcard.csv --model-dir models
```

Restart services that load model artifacts:

```bash
docker compose restart api consumer
```

## Kafka

Internal Docker broker:

```text
kafka:29092
```

Host broker:

```text
localhost:9092
```

Topics:

- `transactions`: raw transaction events produced by `producer/simulator.py`
- `fraud_scores`: scored events emitted by `consumer/scorer.py`

Kafka topic auto-creation is enabled. The `kafka-init` service also explicitly creates both topics on startup.

## Database

PostgreSQL runs on `localhost:5432` with values from `.env`:

```text
POSTGRES_DB=fraudradar
POSTGRES_USER=fraudradar
POSTGRES_PASSWORD=fraudradar
DATABASE_URL=postgresql+psycopg2://fraudradar:fraudradar@postgres:5432/fraudradar
```

The API creates tables on startup for local convenience. Alembic is included for explicit migration workflows:

```bash
alembic upgrade head
```

### Database Tables

| Table | Purpose |
| --- | --- |
| `transaction_scores` | Stores scored transactions, risk details, features, and raw payloads |
| `failed_transactions` | Stores transactions that failed consumer processing |

## Troubleshooting

### Common Issues and Solutions

#### 1. Docker Daemon Not Running

**Symptom:** `Cannot connect to Docker daemon`

**Solution:**
```bash
# Windows (Docker Desktop)
# Open Docker Desktop application

# macOS (Docker Desktop)
# Click Docker icon in menu bar > Open

# Linux
sudo systemctl start docker
```

#### 2. Port Already in Use

**Symptom:** `Error: port 8000 is already in use`

**Solution:**
```bash
# Find what's using the port
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or change port in docker-compose.yml
# Modify: ports: - "8001:8000"
```

#### 3. Containers Fail to Start

**Symptom:** Services stuck at "starting" or immediately crash

**Diagnostic Commands:**
```bash
# Check container status
docker-compose ps

# View logs for specific service
docker-compose logs --tail=50 api
docker-compose logs --tail=50 kafka
docker-compose logs --tail=50 postgres

# Check system resource usage
docker stats
```

**Common Causes & Fixes:**

| Service | Issue | Fix |
|---------|-------|-----|
| **Kafka** | Zookeeper not ready | Wait 30+ seconds, check logs |
| **Postgres** | Port conflict | Kill existing postgres, or change port |
| **API** | Models not found | Models directory missing - run training script |
| **Redis** | Memory exhausted | Reduce cache size or increase Docker memory |
| **All** | Out of disk space | Run `docker system prune -a` |

#### 4. Kafka Topics Not Created

**Symptom:** Kafka topics missing when running `docker-compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list`

**Solution:**
```bash
# Manually run topic initializer
docker-compose up kafka-init

# Verify topics exist
docker-compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list

# Expected output:
# transactions
# fraud_scores
# __consumer_offsets
```

#### 5. API Health Check Fails (Degraded Status)

**Symptom:** `curl http://localhost:8000/health` returns `"status": "degraded"`

**Diagnosis:**
```bash
# Check which service is down
curl http://localhost:8000/health | python -m json.tool

# Example output:
# {
#   "status": "degraded",
#   "kafka": "error",     # <-- Problem here
#   "postgres": "ok",
#   "redis": "ok",
#   "models": "ok"
# }
```

**Solutions by Service:**

| Service | Status: error | Fix |
|---------|---------------|-----|
| **Kafka** | API can't connect | Wait for Kafka startup (60s), check if kafka-init succeeded |
| **Postgres** | Database unavailable | Restart: `docker-compose restart postgres` |
| **Redis** | Cache unavailable | Restart: `docker-compose restart redis` |
| **Models** | ML models missing | Place model files in `models/` or train them |

#### 6. Prometheus Can't Scrape Metrics

**Symptom:** Prometheus shows "DOWN" for api or consumer targets

**Diagnostic:**
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | python -m json.tool

# Check if API metrics endpoint is accessible
curl http://localhost:8000/metrics

# Check if Consumer metrics endpoint is accessible
curl http://localhost:9101/metrics
```

**Solution:**
```bash
# Verify services are healthy
docker-compose ps

# Restart Prometheus
docker-compose restart prometheus

# Check Prometheus config
docker-compose exec prometheus cat /etc/prometheus/prometheus.yml
```

#### 7. Grafana Dashboard Empty (No Data)

**Symptom:** Dashboard shows "no data" in panels

**Causes & Fixes:**
1. **Prometheus not configured** - Check Grafana datasource: http://localhost:3000/datasources
2. **Prometheus empty** - Wait for metrics collection (30s+), or generate load
3. **Metrics not published** - Check if API/Consumer are running and healthy
4. **Query syntax error** - Click on panel title > Edit, check query syntax

**Generate Test Data:**
```bash
# Score multiple transactions to generate metrics
for i in {1..10}; do
  curl -X POST http://localhost:8000/transactions/score \
    -H "Content-Type: application/json" \
    -d "{
      \"amount\": $((RANDOM % 1000)).00,
      \"currency\": \"USD\",
      \"merchant\": \"TestMerchant$i\",
      \"category\": \"test\",
      \"card_id\": \"card_$i\",
      \"customer_id\": \"cus_$i\",
      \"country\": \"US\",
      \"ip_address\": \"192.168.$((RANDOM % 256)).$((RANDOM % 256))\",
      \"device_id\": \"dev_$i\"
    }"
  sleep 0.5
done
```

#### 8. Database Connection Errors

**Symptom:** `FATAL: Ident authentication failed`

**Cause:** PostgreSQL auth issues

**Solution:**
```bash
# Check database is running
docker-compose ps postgres

# Check logs
docker-compose logs --tail=50 postgres

# Reset database
docker-compose down -v
docker-compose up -d postgres
docker-compose logs --tail=20 postgres

# Verify connection
docker-compose exec postgres psql -U fraudradar -d fraudradar -c "SELECT 1;"
```

#### 9. Consumer Not Processing Messages

**Symptom:** Messages in Kafka topic but not in database

**Diagnostic:**
```bash
# Check consumer is running
docker-compose ps consumer

# Check consumer logs
docker-compose logs --tail=100 consumer

# Check if messages are in Kafka
docker-compose exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic transactions \
  --max-messages 5

# Check database has records
docker-compose exec postgres psql -U fraudradar -d fraudradar \
  -c "SELECT COUNT(*) FROM transaction_scores;"
```

**Solution:**
```bash
# Restart consumer
docker-compose restart consumer

# Check if models are present
docker-compose exec consumer ls -la /app/models/

# If no models, copy from host
docker cp models/. fraudradar-consumer:/app/models/
docker-compose restart consumer
```

#### 10. Memory or CPU Issues

**Symptom:** Docker containers using excessive resources or system slow

**Solutions:**
```bash
# Monitor resource usage
docker stats --no-stream

# Reduce data retention (Prometheus)
docker-compose exec prometheus \
  curl -X POST http://localhost:9090/-/reload

# Clear old metrics
docker volume rm fraud_radar_prometheus-data
docker-compose up -d prometheus

# Increase Docker resource limits
# Edit Docker Desktop Settings > Resources > Memory/CPU
```

### Quick Diagnostic Checklist

```bash
# 1. Check all containers are running
docker-compose ps

# 2. Check API health
curl http://localhost:8000/health

# 3. Check Kafka topics
docker-compose exec kafka kafka-topics \
  --bootstrap-server localhost:9092 --list

# 4. Check database records
docker-compose exec postgres psql -U fraudradar -d fraudradar \
  -c "SELECT COUNT(*) FROM transaction_scores;"

# 5. Check Prometheus targets
curl http://localhost:9090/api/v1/targets | python -m json.tool

# 6. Check Grafana datasource
curl http://localhost:3000/api/datasources

# 7. View recent logs
docker-compose logs --tail=50 --follow
```

## Daily Commands Reference

```bash
# Start everything
bash scripts/run_all.sh

# Stop everything
docker-compose down

# Stop and remove data
docker-compose down -v

# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api         # API logs
docker-compose logs -f consumer    # Consumer logs
docker-compose logs -f producer    # Producer logs

# Run tests
pytest tests/ -v

# Access services
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000
# Kafka: localhost:9092
# PostgreSQL: localhost:5432
# Redis: localhost:6379

# Train models (requires data/creditcard.csv)
python -m training.train_isolation_forest \
  --dataset data/creditcard.csv \
  --model-dir models
python -m training.train_autoencoder \
  --dataset data/creditcard.csv \
  --model-dir models
```

## Key Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| **API** | http://localhost:8000 | REST endpoints |
| **API Docs** | http://localhost:8000/docs | Swagger UI |
| **API ReDoc** | http://localhost:8000/redoc | Alternative docs |
| **Grafana** | http://localhost:3000 | Dashboards (admin/admin) |
| **Prometheus** | http://localhost:9090 | Metrics queries |
| **Metrics (API)** | http://localhost:8000/metrics | Prometheus format |
| **Metrics (Consumer)** | http://localhost:9101/metrics | Prometheus format |
| **Database** | localhost:5432 | PostgreSQL |
| **Cache** | localhost:6379 | Redis |
| **Message Broker** | localhost:9092 | Kafka |
| **Coordination** | localhost:2181 | Zookeeper |

## Metrics Exported

**From API (`/metrics`):**
- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency
- `fraudradar_transactions_total` - Transactions scored
- `fraudradar_fraud_detected_total` - Fraud cases detected

**From Consumer (`:9101/metrics`):**
- `fraudradar_scoring_latency_seconds` - Scoring performance
- `fraudradar_risk_score` - Risk score distribution
- `fraudradar_consumer_errors_total` - Processing errors

## Support & Resources

- **API Documentation:** http://localhost:8000/docs
- **Prometheus Query Help:** http://localhost:9090/graph (click "Metrics")
- **Grafana Help:** http://localhost:3000/help
- **Kafka Topics:** `docker-compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list`
- **Database Schema:** Check `api/models_db.py`

## Current Status

The project now contains a working end-to-end fraud detection stack:

- Transactions can be generated continuously.
- Kafka can stream raw and scored transaction events.
- The consumer can score and persist transactions.
- The API can score transactions on demand and expose stored results.
- PostgreSQL, Redis, Prometheus, and Grafana are wired into the system.
- Comprehensive tests and setup scripts are included for validation and local use.
- Full troubleshooting guide and daily command reference provided.


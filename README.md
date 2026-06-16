# 🛡️ FraudRadar
> Real-time fraud detection API — Stripe Radar inspired, runs 100% locally via Docker.

Streams fake transactions through Kafka, scores them with ML (Isolation Forest + Autoencoder), stores results in PostgreSQL, and visualizes everything in Grafana.

---

## ⚡ Quick Start

```bash
git clone https://github.com/Mayankkkkk2207/FraudRadar.git
cd FraudRadar
bash scripts/run_all.sh
```

| Service | URL |
|---|---|
| API Docs | http://localhost:8000/docs |
| Grafana | http://localhost:3000 (admin/admin) |
| Prometheus | http://localhost:9090 |

---

## 🏗️ Architecture

```
Producer → Kafka → Consumer (ML Scoring) → PostgreSQL + Redis
                                         ↓
                              FastAPI (Port 8000)
                                         ↓
                         Prometheus → Grafana (Port 3000)
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | System health check |
| `POST` | `/transactions/score` | Score a transaction |
| `GET` | `/transactions` | List (paginated, filterable) |
| `GET` | `/transactions/{id}` | Single transaction |
| `GET` | `/stats` | Fraud stats & breakdown |
| `GET` | `/docs` | Swagger UI |
| `GET` | `/metrics` | Prometheus metrics |

### Score a Transaction

```bash
curl -X POST http://localhost:8000/transactions/score \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 4999.99,
    "currency": "USD",
    "merchant": "TestShop",
    "card_id": "card_123",
    "customer_id": "cus_456",
    "country": "RU",
    "device_id": "dev_789"
  }'
```

---

## 🧠 ML Models

| Model | Purpose | File |
|---|---|---|
| Isolation Forest | Anomaly detection | `models/isolation_forest.joblib` |
| Autoencoder | Reconstruction error | `models/autoencoder.keras` |
| Rules Engine | Business heuristics | Built-in |

Risk levels: `LOW` → `MEDIUM` → `HIGH` → `CRITICAL`

---

## 🐳 Services

| Service | Port |
|---|---|
| FastAPI | 8000 |
| Grafana | 3000 |
| Prometheus | 9090 |
| Kafka | 9092 |
| PostgreSQL | 5432 |
| Redis | 6379 |
| Zookeeper | 2181 |

---

## 🧪 Tests

```bash
pip install pytest pytest-asyncio httpx
pytest tests/ -v
```

---

## 🛑 Stop / Reset

```bash
docker-compose down          # Stop (keep data)
docker-compose down -v       # Stop + wipe data
```

---

## 🔧 Train Models (Optional)

Models are pre-trained. To retrain with Kaggle dataset:

```bash
# Place creditcard.csv in data/
python -m training.train_isolation_forest --dataset data/creditcard.csv
python -m training.train_autoencoder --dataset data/creditcard.csv
docker-compose restart api consumer
```

Dataset: [Kaggle Credit Card Fraud Detection](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud)

---

## 🆘 Common Fixes

| Problem | Fix |
|---|---|
| Container not starting | `docker-compose logs [service]` |
| Kafka not ready | Wait 60s after startup |
| API health degraded | `docker-compose restart [failed-service]` |
| No data in Grafana | Score a few transactions to generate metrics |
| Port in use | `docker-compose down` then `up` again |

---

## 📁 Structure

```
FraudRadar/
├── api/          FastAPI app + routes + schemas
├── consumer/     Kafka consumer + ML scorer
├── producer/     Transaction simulator
├── fraudradar/   Shared scoring + feature logic
├── training/     Model training scripts
├── models/       Trained model artifacts
├── monitoring/   Prometheus + Grafana config
├── tests/        API test suite (30+ tests)
└── docker-compose.yml
```

---

**Tech Stack:** Python · FastAPI · Apache Kafka · Scikit-learn · TensorFlow · PostgreSQL · Redis · Docker · Prometheus · Grafana

**Author:** [Mayank](https://github.com/Mayankkkkk2207) · MIT License
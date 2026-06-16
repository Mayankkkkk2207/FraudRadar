#!/bin/bash
# FraudRadar Complete System Startup Script
# This script brings up the entire fraud detection system with all dependencies

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "=========================================="
echo "FraudRadar System Initialization"
echo "=========================================="

# Step 1: Clean slate
echo ""
echo "[1/7] Cleaning up existing containers and volumes..."
docker-compose down --volumes 2>/dev/null || true
echo "✓ Cleaned up"

# Step 2: Start infrastructure services
echo ""
echo "[2/7] Starting infrastructure (Zookeeper, Kafka, PostgreSQL, Redis)..."
docker-compose up -d zookeeper kafka postgres redis
echo "✓ Infrastructure services started"

# Step 3: Wait for services to be healthy
echo ""
echo "[3/7] Waiting 30 seconds for services to stabilize..."
sleep 5
echo "  - Waiting for Zookeeper..."
docker-compose exec -T zookeeper bash -c 'until echo srvr | nc -w 2 localhost 2181 | grep Mode; do sleep 1; done' || true
sleep 2

echo "  - Waiting for Kafka..."
docker-compose exec -T kafka bash -c 'until kafka-broker-api-versions --bootstrap-server localhost:9092; do sleep 1; done' || true
sleep 2

echo "  - Waiting for PostgreSQL..."
docker-compose exec -T postgres bash -c 'until pg_isready -U fraudradar; do sleep 1; done' || true
sleep 2

echo "  - Waiting for Redis..."
docker-compose exec -T redis redis-cli ping > /dev/null || true
sleep 10

echo "✓ Infrastructure services are healthy"

# Step 4: Verify Kafka topics
echo ""
echo "[4/7] Initializing Kafka topics..."
docker-compose up kafka-init
echo "✓ Kafka topics ready"

# Step 5: Start application services
echo ""
echo "[5/7] Starting application services (API, Producer, Consumer, Prometheus, Grafana)..."
docker-compose up -d api producer consumer prometheus grafana
echo "✓ Application services started"

# Step 6: Wait for application services to be healthy
echo ""
echo "[6/7] Waiting for application services to be ready..."
sleep 10
for i in {1..30}; do
  API_HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null | grep -o '"status":"ok"' || echo "")
  if [ -n "$API_HEALTH" ]; then
    echo "✓ API is healthy"
    break
  fi
  if [ $i -eq 30 ]; then
    echo "⚠ API health check timed out (may still be starting)"
  fi
  sleep 1
done

# Step 7: Print service URLs
echo ""
echo "[7/7] Startup complete!"
echo ""
echo "=========================================="
echo "FraudRadar Services are Ready!"
echo "=========================================="
echo ""
echo "API Endpoints:"
echo "  - API: http://localhost:8000"
echo "  - API Docs (Swagger): http://localhost:8000/docs"
echo "  - API ReDoc: http://localhost:8000/redoc"
echo "  - Health Check: http://localhost:8000/health"
echo ""
echo "Monitoring & Analytics:"
echo "  - Prometheus: http://localhost:9090"
echo "  - Grafana: http://localhost:3000"
echo "    - Default credentials: admin / admin"
echo "    - Dashboard: FraudRadar Dashboard"
echo ""
echo "Infrastructure:"
echo "  - Kafka: localhost:9092"
echo "  - PostgreSQL: localhost:5432 (user: fraudradar, db: fraudradar)"
echo "  - Redis: localhost:6379"
echo "  - Zookeeper: localhost:2181"
echo ""
echo "To stop all services:"
echo "  docker-compose down"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f [service_name]"
echo ""
echo "To run tests:"
echo "  python -m pytest tests/ -v"
echo ""
echo "=========================================="

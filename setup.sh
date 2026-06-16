#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "==> Creating project folders"
mkdir -p \
  alembic/versions \
  api/routes \
  consumer \
  data \
  fraudradar \
  models \
  monitoring/grafana/dashboards \
  monitoring/grafana/provisioning/dashboards \
  monitoring/grafana/provisioning/datasources \
  producer \
  training

print_kaggle_help() {
  cat <<'EOF'

Kaggle dataset download was skipped or failed.

To enable automatic download:
  1. Create a Kaggle API token at https://www.kaggle.com/settings
  2. Save kaggle.json to ~/.kaggle/kaggle.json
  3. Run: chmod 600 ~/.kaggle/kaggle.json
  4. Install the CLI if needed: pip install kaggle
  5. Re-run: bash setup.sh

Manual fallback:
  Download "Credit Card Fraud Detection" from:
  https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud
  Then place creditcard.csv at data/creditcard.csv

FraudRadar can still start without the CSV. The app will bootstrap local model artifacts
if trained models are not present.
EOF
}

echo "==> Checking Kaggle dataset"
if [[ -f data/creditcard.csv ]]; then
  echo "data/creditcard.csv already exists; skipping Kaggle download."
elif command -v kaggle >/dev/null 2>&1; then
  if kaggle datasets download -d mlg-ulb/creditcardfraud -p data --unzip; then
    echo "Kaggle dataset downloaded into data/."
  else
    print_kaggle_help
  fi
else
  print_kaggle_help
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "Docker Compose was not found. Install Docker Desktop or Docker Engine with Compose." >&2
  exit 1
fi

echo "==> Starting FraudRadar stack"
"${COMPOSE[@]}" up -d --build

wait_for_health() {
  local container="$1"
  local timeout_seconds="${2:-360}"
  local started_at
  started_at="$(date +%s)"

  while true; do
    local status
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null || true)"

    if [[ "$status" == "healthy" ]]; then
      echo "$container is healthy."
      return 0
    fi

    if [[ "$status" == "exited" || "$status" == "dead" ]]; then
      echo "$container stopped before becoming healthy." >&2
      docker logs "$container" --tail 80 >&2 || true
      return 1
    fi

    local now
    now="$(date +%s)"
    if (( now - started_at >= timeout_seconds )); then
      echo "Timed out waiting for $container to become healthy. Last status: ${status:-unknown}" >&2
      docker logs "$container" --tail 80 >&2 || true
      return 1
    fi

    sleep 5
  done
}

echo "==> Verifying container health"
containers=(
  fraudradar-zookeeper
  fraudradar-kafka
  fraudradar-postgres
  fraudradar-redis
  fraudradar-api
  fraudradar-producer
  fraudradar-consumer
  fraudradar-prometheus
  fraudradar-grafana
)

for container in "${containers[@]}"; do
  wait_for_health "$container" 420
done

echo "==> Verifying Kafka topic initialization"
kafka_init_id="$("${COMPOSE[@]}" ps -q kafka-init)"
if [[ -z "$kafka_init_id" ]]; then
  echo "Could not find kafka-init container." >&2
  exit 1
fi

kafka_init_exit_code="$(docker inspect --format '{{.State.ExitCode}}' "$kafka_init_id")"
if [[ "$kafka_init_exit_code" != "0" ]]; then
  echo "kafka-init failed with exit code $kafka_init_exit_code." >&2
  docker logs "$kafka_init_id" >&2 || true
  exit 1
fi

echo "==> Kafka topics"
"${COMPOSE[@]}" exec -T kafka kafka-topics --bootstrap-server localhost:9092 --list

cat <<'EOF'

FraudRadar is ready.

API docs:    http://localhost:8000/docs
API health:  http://localhost:8000/health
Prometheus:  http://localhost:9090
Grafana:     http://localhost:3000
EOF

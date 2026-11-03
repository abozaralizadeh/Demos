#!/usr/bin/env bash
# Run on the VM. First run installs everything, every later run updates and restarts it.
# Logs: journalctl -u demos-api.service -f (also demos-identity, demos-worker)
# Copyable log files: logs/ in the project root (10MB x 3 files, so they can't grow forever)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_USER="${SUDO_USER:-$USER}"

if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$RUN_USER"
fi
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
UV="$(command -v uv)"

# Real secrets are made once and never overwritten.
if [ ! -f "$ROOT/.env" ]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  for key in DEMOS_SESSION_SECRET DEMOS_ASSERTION_SECRET DEMOS_IDENTITY_PEPPER DEMOS_SERVICE_TOKEN DEMOS_REVIEW_TOKEN; do
    sed -i "s|^$key=.*|$key=$(openssl rand -hex 32)|" "$ROOT/.env"
  done
  chmod 600 "$ROOT/.env"
fi

sudo docker compose -f "$ROOT/docker-compose.yml" up -d
until sudo docker compose -f "$ROOT/docker-compose.yml" exec -T postgres pg_isready -U demos -d demos_identity >/dev/null 2>&1; do
  sleep 1
done

cd "$ROOT/backend"
"$UV" sync --no-dev
"$UV" run python -c "from demos.db import connect, migrate
with connect() as conn:
    migrate(conn)"

# Sample data goes in once, so a restart never resets it.
if [ ! -f "$ROOT/.seeded" ]; then
  "$UV" run python -m demos.seed
  touch "$ROOT/.seeded"
fi

write_unit() {
  sudo tee "/etc/systemd/system/$1.service" >/dev/null <<EOF
[Unit]
Description=$1
After=network.target docker.service

[Service]
User=$RUN_USER
WorkingDirectory=$ROOT/backend
ExecStart=$2
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
}

write_unit demos-identity "$UV run uvicorn demos.identity_service:app --host 127.0.0.1 --port 8001"
write_unit demos-api "$UV run uvicorn demos.api:app --host 0.0.0.0 --port 8000"
write_unit demos-worker "$UV run python -m demos.worker"

sudo systemctl daemon-reload
sudo systemctl enable demos-identity demos-api demos-worker
sudo systemctl restart demos-identity demos-api demos-worker

echo "Demos is up. Logs: journalctl -u demos-api.service -f"

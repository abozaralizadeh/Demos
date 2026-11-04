#!/usr/bin/env bash
# Installs and updates Demos on a Linux VM. Running it again updates and restarts everything.
#
# Standalone, on a VM of its own (installs Docker and uv if they're missing):
#
#   ./setup_service.sh
#   Logs: journalctl -u demos-api.service -f (also demos-identity, demos-worker)
#
# Shared VM, behind an nginx you already run, under a path such as /demos/:
#
#   sudo SERVICE_NAME=demos PORT=8608 BASE_PATH=/demos/ \
#        NGINX_SNIPPET=/etc/nginx/snippets/demos.conf ./setup_service.sh
#
#   Installs nothing: it stops and says so if docker, docker compose, nginx, curl or Python 3.12
#   is missing. Postgres runs in Docker as <service>-postgres-1 on 127.0.0.1 only, with its volume
#   and network named after the service too, and nothing else in Docker is touched. One unit,
#   <service>.service, runs the API on 127.0.0.1:PORT plus identity (on a unix socket) and the
#   worker. It writes two nginx files, NGINX_SNIPPET and /etc/nginx/conf.d/<service>-limits.conf,
#   runs nginx -t, and removes both again if the check fails. Your server block must include the
#   snippet (for example: include /etc/nginx/snippets/demos.conf;).
#   Add PG_PORT=<port> if 5608 is taken. PRINT_NGINX=1 only prints the two nginx files.
#   Logs: journalctl -u <service> -f
#
# Both modes keep an existing .env. Copyable log files are in logs/ (10MB x 3 files each).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

die() { echo "$*" >&2; exit 1; }
env_get() { grep -E "^$1=" "$ROOT/.env" 2>/dev/null | tail -1 | cut -d= -f2- || true; }
set_env() { # set_env KEY VALUE  (adds or replaces the line)
  if grep -q "^$1=" "$ROOT/.env"; then sed -i "s|^$1=.*|$1=$2|" "$ROOT/.env"; else echo "$1=$2" >> "$ROOT/.env"; fi
}
port_busy() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }
SECRETS="DEMOS_SESSION_SECRET DEMOS_ASSERTION_SECRET DEMOS_IDENTITY_PEPPER DEMOS_SERVICE_TOKEN DEMOS_REVIEW_TOKEN"

nginx_files() { # nginx_files SERVICE BASE PORT ZONE_FILE SNIPPET
  local zone="${1//-/_}"
  cat > "$4" <<NGINX
# $1: rate limit zone, used by $NGINX_SNIPPET
limit_req_zone \$binary_remote_addr zone=${zone}:10m rate=5r/s;
NGINX
  cat > "$5" <<NGINX
# $1: written by setup_service.sh in $ROOT
location = ${2%/} { return 301 $2; }
location $2 {
    limit_req zone=${zone} burst=20 nodelay;
    limit_req_status 429;
    client_max_body_size 16k;
    proxy_pass http://127.0.0.1:$3/;
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Forwarded-For \$remote_addr;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_set_header Connection "";
    # A turn can wait on the AI a few times before it answers
    proxy_read_timeout 120s;
}
NGINX
}

shared() {
  local SERVICE="${SERVICE_NAME:-demos}" APP_PORT="${PORT:-8608}" BASE="${BASE_PATH:-/demos/}"
  [[ "$SERVICE" =~ ^[a-z0-9][a-z0-9-]*$ ]] || die "SERVICE_NAME can only have lower case letters, digits and dashes."
  [[ "$BASE" == /*/ ]] || die "BASE_PATH must start and end with a slash, like /demos/"
  [[ "$APP_PORT" =~ ^[0-9]+$ ]] || die "PORT must be a number."
  local ZONE_FILE="/etc/nginx/conf.d/${SERVICE}-limits.conf"

  if [[ -n "${PRINT_NGINX:-}" ]]; then
    local tmp; tmp="$(mktemp -d)"
    nginx_files "$SERVICE" "$BASE" "$APP_PORT" "$tmp/zone" "$tmp/snippet"
    echo "# $ZONE_FILE"; cat "$tmp/zone"; echo; echo "# $NGINX_SNIPPET"; cat "$tmp/snippet"
    rm -rf "$tmp"; return
  fi
  [[ $EUID -eq 0 ]] || die "Run this with sudo."

  local RUN_USER RUN_GROUP RUN_HOME
  RUN_USER="${SERVICE_USER:-$(stat -c %U "$ROOT")}"
  RUN_GROUP="$(id -gn "$RUN_USER")"
  RUN_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"
  as_user() { sudo -u "$RUN_USER" -H env PATH="$PATH" "$@"; }

  echo "==> Checking what's already here (this mode installs nothing)"
  local missing=() PY_SYS UV
  for c in docker nginx curl systemctl sudo; do command -v "$c" >/dev/null || missing+=("$c"); done
  command -v docker >/dev/null && ! docker compose version >/dev/null 2>&1 && missing+=("docker compose")
  PY_SYS="$(command -v python3.12 || command -v python3.13 || command -v python3 || true)"
  if [[ -z "$PY_SYS" ]] || ! "$PY_SYS" -c 'import sys; sys.exit(sys.version_info[:2] not in ((3, 12), (3, 13)))'; then
    missing+=("Python 3.12")
  fi
  UV="$(command -v uv || true)"
  [[ -z "$UV" && -x "$RUN_HOME/.local/bin/uv" ]] && UV="$RUN_HOME/.local/bin/uv"
  if [[ -z "$UV" && -n "$PY_SYS" ]] && ! "$PY_SYS" -c 'import venv, ensurepip' 2>/dev/null; then
    missing+=("python3.12-venv (or uv)")
  fi
  ((${#missing[@]} == 0)) || die "Missing: ${missing[*]}. Add them first, then run this again. Nothing was changed."
  [[ -f /etc/nginx/nginx.conf ]] && grep -qE 'include\s+/etc/nginx/conf\.d/\*\.conf' /etc/nginx/nginx.conf \
    || die "nginx.conf doesn't include conf.d, so the rate limit zone can't be added. Nothing was changed."

  if [[ -d .git && "${GIT_PULL:-true}" == true ]]; then
    echo "==> Latest code"
    # Fast forward only, so local changes are never thrown away. Set GIT_PULL=false to skip.
    as_user git pull --ff-only || echo "    could not fast forward, setting up what is here"
  fi

  echo "==> Settings"
  token() { "$PY_SYS" -c 'import secrets; print(secrets.token_hex(32))'; }
  if [[ ! -f .env ]]; then
    cp .env.example .env
    for key in $SECRETS; do set_env "$key" "$(token)"; done
    set_env DEMOS_PG_PASSWORD "$(token)"
    set_env DEMOS_PG_PORT "${PG_PORT:-5608}"
    echo "    made .env with new secrets. Add the AZURE_OPENAI_ values to it for real AI replies."
  fi
  [[ -n "${PG_PORT:-}" ]] && set_env DEMOS_PG_PORT "$PG_PORT"
  local PG_PASS PGP
  PG_PASS="$(env_get DEMOS_PG_PASSWORD)"; PGP="$(env_get DEMOS_PG_PORT)"; PGP="${PGP:-5433}"
  if [[ -n "$PG_PASS" ]]; then
    set_env DEMOS_DATABASE_URL "postgresql://demos:${PG_PASS}@127.0.0.1:${PGP}/demos"
    set_env DEMOS_IDENTITY_DATABASE_URL "postgresql://demos:${PG_PASS}@127.0.0.1:${PGP}/demos_identity"
  fi
  set_env PORT "$APP_PORT"
  set_env BASE_PATH "$BASE"
  # Behind the local nginx, trust only it for the client address.
  set_env TRUST_PROXY 127.0.0.1
  set_env DEMOS_IDENTITY_SOCKET "$ROOT/run/identity.sock"
  mkdir -p logs run
  chown -R "$RUN_USER:$RUN_GROUP" .env logs run
  chmod 600 .env

  echo "==> Postgres in Docker (${SERVICE}-postgres-1 on 127.0.0.1:${PGP})"
  compose() { docker compose -p "$SERVICE" -f "$ROOT/docker-compose.yml" --env-file "$ROOT/.env" "$@"; }
  if [[ -z "$(compose ps -q postgres 2>/dev/null)" ]] && port_busy "$PGP"; then
    die "Port $PGP is already taken by something else. Run again with PG_PORT=<a free port>."
  fi
  compose up -d postgres
  until compose exec -T postgres pg_isready -U demos -d demos_identity >/dev/null 2>&1; do sleep 1; done

  echo "==> Python packages"
  cd "$ROOT/backend"
  if [[ -n "$UV" ]]; then
    as_user env UV_PYTHON_DOWNLOADS=never "$UV" sync --no-dev --frozen --python "$PY_SYS"
  else
    [[ -x .venv/bin/python ]] || as_user "$PY_SYS" -m venv .venv
    as_user .venv/bin/pip install -q --disable-pip-version-check --require-hashes -r requirements.txt
  fi
  local PY="$ROOT/backend/.venv/bin/python"
  as_user "$PY" -c "from demos.db import connect, migrate
with connect() as conn:
    migrate(conn)"
  # Sample data goes in once, so a restart never resets it.
  if [[ ! -f "$ROOT/.seeded" ]]; then
    as_user "$PY" -m demos.seed
    as_user touch "$ROOT/.seeded"
  fi
  cd "$ROOT"

  echo "==> Service ${SERVICE}.service on 127.0.0.1:${APP_PORT}"
  if ! systemctl is-active --quiet "${SERVICE}.service" && port_busy "$APP_PORT"; then
    die "Port $APP_PORT is already taken by something else. Pick another PORT."
  fi
  cat > "/etc/systemd/system/${SERVICE}.service" <<UNIT
[Unit]
Description=Demos (${SERVICE})
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_GROUP}
WorkingDirectory=${ROOT}/backend
EnvironmentFile=${ROOT}/.env
Environment=PYTHON=${PY}
ExecStart=${ROOT}/backend/serve.sh
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full

[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  systemctl enable "${SERVICE}.service" >/dev/null
  systemctl restart "${SERVICE}.service"

  echo "==> nginx: ${BASE} -> 127.0.0.1:${APP_PORT}"
  # Old copies wait in a temp folder, so only the two files ever appear in /etc/nginx.
  local keep; keep="$(mktemp -d)"
  [[ -f "$NGINX_SNIPPET" ]] && cp -p "$NGINX_SNIPPET" "$keep/snippet"
  [[ -f "$ZONE_FILE" ]] && cp -p "$ZONE_FILE" "$keep/zone"
  mkdir -p "$(dirname "$NGINX_SNIPPET")"
  nginx_files "$SERVICE" "$BASE" "$APP_PORT" "$ZONE_FILE" "$NGINX_SNIPPET"
  if nginx -t 2>"$keep/test.log"; then
    systemctl reload nginx
    rm -rf "$keep"
  else
    cat "$keep/test.log" >&2
    if [[ -f "$keep/snippet" ]]; then cp -p "$keep/snippet" "$NGINX_SNIPPET"; else rm -f "$NGINX_SNIPPET"; fi
    if [[ -f "$keep/zone" ]]; then cp -p "$keep/zone" "$ZONE_FILE"; else rm -f "$ZONE_FILE"; fi
    rm -rf "$keep"
    die "nginx -t failed, so both nginx files were put back as they were. The service itself is running."
  fi

  echo "==> Check"
  for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:${APP_PORT}/health" >/dev/null 2>&1; then
      echo "    up at ${BASE} (AI: $(curl -fsS "http://127.0.0.1:${APP_PORT}/health" | "$PY_SYS" -c 'import json,sys; print(json.load(sys.stdin)["ai"])'))"
      echo "    Logs: journalctl -u ${SERVICE} -f   Files: ${ROOT}/logs/"
      return
    fi
    sleep 1
  done
  die "The service did not come up. Look at: journalctl -u ${SERVICE} -n 50"
}

standalone() {
  local RUN_USER="${SUDO_USER:-$USER}"
  if ! command -v docker >/dev/null; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$RUN_USER"
  fi
  if ! command -v uv >/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
  fi
  local UV; UV="$(command -v uv)"

  # Real secrets are made once and never overwritten.
  if [ ! -f "$ROOT/.env" ]; then
    cp "$ROOT/.env.example" "$ROOT/.env"
    for key in $SECRETS; do
      sed -i "s|^$key=.*|$key=$(openssl rand -hex 32)|" "$ROOT/.env"
    done
    chmod 600 "$ROOT/.env"
  fi
  mkdir -p "$ROOT/logs"

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
EnvironmentFile=$ROOT/.env
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
}

if [[ -n "${NGINX_SNIPPET:-}" ]]; then shared; else standalone; fi

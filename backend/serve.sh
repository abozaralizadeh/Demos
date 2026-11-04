#!/usr/bin/env bash
# Runs identity, the worker and the API together, so one systemd unit (and one journal) holds Demos.
# setup_service.sh points the unit here on a shared VM. If any of the three stops, the others stop
# too and systemd starts all three again.
#
# Reads from the environment (the unit loads .env): PORT, BASE_PATH, TRUST_PROXY, DEMOS_IDENTITY_SOCKET,
# and PYTHON for the venv's python.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
PY="${PYTHON:-.venv/bin/python}"
SOCK="${DEMOS_IDENTITY_SOCKET:?DEMOS_IDENTITY_SOCKET is not set}"
BASE="${BASE_PATH:-/}"

# Only this user can reach the identity socket, so other apps on the VM can't.
umask 077
mkdir -p "$(dirname "$SOCK")"
rm -f "$SOCK"
pids=()
"$PY" -m uvicorn demos.identity_service:app --uds "$SOCK" --no-access-log & pids+=($!)
"$PY" -m demos.worker & pids+=($!)
"$PY" -m uvicorn demos.api:app --host 127.0.0.1 --port "${PORT:-8000}" \
  --proxy-headers --forwarded-allow-ips "${TRUST_PROXY:-127.0.0.1}" --root-path "${BASE%/}" & pids+=($!)

trap 'kill "${pids[@]}" 2>/dev/null' EXIT
trap 'exit 143' TERM INT
while kill -0 "${pids[@]}" 2>/dev/null; do sleep 2; done
echo "a Demos process stopped, so the service restarts" >&2
exit 1

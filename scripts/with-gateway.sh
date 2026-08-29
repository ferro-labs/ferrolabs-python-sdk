#!/usr/bin/env bash
# Boot a real AI Gateway checkout against a stub upstream, run the SDK
# contract suite against it, and always tear both down.
#
#   FERRO_GATEWAY_SOURCE=../ai-gateway ./scripts/with-gateway.sh [pytest args]
#
# Adapted from gateway-cli/scripts/with-gateway.sh. This is the one check the
# pytest-httpx unit suite cannot perform: the unit tests prove the SDK is
# correct given a gateway that behaves as documented; only this proves the
# real server agrees. A divergence found here is a contract drift — fix the
# SDK (or the docs) to match the gateway, then re-run.
#
# No provider credentials are required. tests/contract/stub_upstream.py plays
# the OpenAI API and the gateway is pointed at it via OPENAI_BASE_URL, which
# is enough to exercise probes, the catalog, chat, streaming, embeddings,
# responses, the error envelope, and every /admin/* route the SDK wraps.
#
# Env: FERRO_GATEWAY_SOURCE (default ../ai-gateway), FERRO_CONTRACT_PORT
# (default 18080), FERRO_CONTRACT_STUB_PORT (default 18081), PYTHON (default
# python3 — point it at a venv interpreter with ferrolabsai[dev] installed).
set -euo pipefail

for tool in curl go; do
  command -v "$tool" >/dev/null || { echo "$tool is required" >&2; exit 2; }
done
python="${PYTHON:-python3}"
command -v "$python" >/dev/null || { echo "$python is required (set PYTHON)" >&2; exit 2; }

sdk="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
gateway_source="${FERRO_GATEWAY_SOURCE:-}"
if [ -z "$gateway_source" ]; then
  candidate="$(cd "$sdk/.." && pwd)/ai-gateway"
  if [ -f "$candidate/go.mod" ] && grep -q '^module github.com/ferro-labs/ai-gateway$' "$candidate/go.mod"; then
    gateway_source="$candidate"
  else
    echo "FERRO_GATEWAY_SOURCE must point to an AI Gateway checkout" >&2
    exit 2
  fi
fi
gateway_source="$(cd "$gateway_source" && pwd)"
work="$(mktemp -d)"
port="${FERRO_CONTRACT_PORT:-18080}"
stub_port="${FERRO_CONTRACT_STUB_PORT:-18081}"
gw_pid=""
stub_pid=""

# A hex master key of the shape the gateway expects (fgw_ + 32 hex chars).
key="fgw_$(od -An -tx1 -N16 /dev/urandom | tr -d ' \n')"

cleanup() {
  for pid in "$gw_pid" "$stub_pid"; do
    if [ -n "$pid" ]; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
  rm -rf "$work"
}
trap cleanup EXIT

# Poll a URL until it answers with one of the given status codes.
wait_for() {
  local url="$1" pid="$2" name="$3"; shift 3
  local deadline=$((SECONDS + 30)) code
  while (( SECONDS < deadline )); do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "$name exited during startup; log follows:" >&2
      cat "$work/$name.log" >&2
      exit 1
    fi
    code="$(curl -sS --connect-timeout 1 --max-time 2 -o /dev/null -w '%{http_code}' "$url" 2>/dev/null)" || code=""
    for ok in "$@"; do [ "$code" = "$ok" ] && return 0; done
    sleep 0.25
  done
  echo "$name did not answer $url within 30s; log follows:" >&2
  cat "$work/$name.log" >&2
  exit 1
}

echo "==> starting stub upstream on :$stub_port"
"$python" "$sdk/tests/contract/stub_upstream.py" --port "$stub_port" >"$work/stub.log" 2>&1 &
stub_pid=$!
wait_for "http://127.0.0.1:$stub_port/v1/models" "$stub_pid" stub 200

echo "==> building ferrogw from $gateway_source"
(cd "$gateway_source" && go build -o "$work/ferrogw" ./cmd/ferrogw)

echo "==> writing a throwaway config (one openai target routed to the stub)"
# persist: true so /admin/logs and /admin/logs/stats have rows to return; the
# store itself is the SQLite file named by REQUEST_LOG_STORE_DSN below.
cat >"$work/gateway.yaml" <<'YAML'
apiVersion: v1
strategy:
  mode: single
targets:
  - virtual_key: openai
plugins:
  - name: request-logger
    type: logging
    stage: before_request
    enabled: true
    config: { level: info, persist: true }
  - name: request-logger
    type: logging
    stage: after_request
    enabled: true
    config: { level: info, persist: true }
  - name: request-logger
    type: logging
    stage: on_error
    enabled: true
    config: { level: info, persist: true }
YAML

echo "==> starting gateway on :$port"
MASTER_KEY="$key" GATEWAY_CONFIG="$work/gateway.yaml" PORT="$port" \
  REQUEST_LOG_STORE_BACKEND=sqlite REQUEST_LOG_STORE_DSN="$work/requestlog.db" \
  OPENAI_API_KEY=stub-key OPENAI_BASE_URL="http://127.0.0.1:$stub_port/v1" \
  "$work/ferrogw" serve >"$work/gateway.log" 2>&1 &
gw_pid=$!

# /health answers 503 when degraded (still JSON, still "up"); /readyz must be 200
# because the whole point of the stub is a routable target.
wait_for "http://127.0.0.1:$port/health" "$gw_pid" gateway 200 503
wait_for "http://127.0.0.1:$port/readyz" "$gw_pid" gateway 200

echo "==> verifying the stub's models are routable through the gateway"
if ! curl -sS -H "Authorization: Bearer $key" "http://127.0.0.1:$port/v1/models" | grep -q '"gpt-4o-mini"'; then
  echo "gateway /v1/models does not list the stub's gpt-4o-mini; log follows:" >&2
  cat "$work/gateway.log" >&2
  exit 1
fi

echo "==> running the contract suite"
cd "$sdk"
FERRO_CONTRACT_BASE_URL="http://127.0.0.1:$port" \
  FERRO_CONTRACT_MASTER_KEY="$key" \
  FERRO_CONTRACT_STUB_URL="http://127.0.0.1:$stub_port" \
  "$python" -m pytest tests/contract -v "$@"

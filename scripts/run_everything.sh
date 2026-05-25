#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
ENV_FILE="$ROOT_DIR/.env"
ENV_EXAMPLE="$ROOT_DIR/.env.example"
BACKEND_VENV="$BACKEND_DIR/.venv"
BACKEND_STAMP="$BACKEND_VENV/.hireos_requirements_installed"
FRONTEND_STAMP="$FRONTEND_DIR/node_modules/.hireos_deps_installed"
FRONTEND_NEXT_LOCK="$FRONTEND_DIR/.next/dev/lock"
STOP_TIMEOUT_SECONDS="${STOP_TIMEOUT_SECONDS:-2}"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
HOST="${HOST:-127.0.0.1}"
SEED_DATA="true"
INSTALL_DEPS="true"
USE_DOCKER="false"

print_help() {
  cat <<'EOF'
Usage: scripts/run_everything.sh [options]

Starts the full local HireOS AI demo in one command.

Options:
  --docker         Run docker compose up --build instead of local dev servers
  --no-install     Skip dependency installation checks
  --no-seed        Skip backend seed step
  --help           Show this message

Environment overrides:
  HOST             Default: 127.0.0.1
  BACKEND_PORT     Default: 8000
  FRONTEND_PORT    Default: 3000
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --docker)
      USE_DOCKER="true"
      shift
      ;;
    --no-install)
      INSTALL_DEPS="false"
      shift
      ;;
    --no-seed)
      SEED_DATA="false"
      shift
      ;;
    --help|-h)
      print_help
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      print_help
      exit 1
      ;;
  esac
done

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

collect_child_pids() {
  local pid="$1"
  local child

  for child in $(pgrep -P "$pid" 2>/dev/null || true); do
    echo "$child"
    collect_child_pids "$child"
  done
}

any_process_alive() {
  local pid
  for pid in "$@"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      return 0
    fi
  done
  return 1
}

dedupe_pids() {
  awk '!seen[$0]++'
}

stop_processes() {
  local label="$1"
  shift
  local root_pid
  local target
  local waited=0
  local -a targets=()

  if [[ $# -eq 0 ]]; then
    return
  fi

  while IFS= read -r target; do
    [[ -n "$target" ]] && targets+=("$target")
  done < <(
    for root_pid in "$@"; do
      if kill -0 "$root_pid" >/dev/null 2>&1; then
        echo "$root_pid"
        collect_child_pids "$root_pid"
      fi
    done | dedupe_pids
  )

  if [[ ${#targets[@]} -eq 0 ]]; then
    return
  fi

  echo "Stopping $label process: ${targets[*]}"
  kill "${targets[@]}" >/dev/null 2>&1 || true

  while any_process_alive "${targets[@]}"; do
    if [[ "$waited" -ge $((STOP_TIMEOUT_SECONDS * 10)) ]]; then
      echo "$label process ${targets[*]} did not stop gracefully. Forcing stop..." >&2
      kill -9 "${targets[@]}" >/dev/null 2>&1 || true
      break
    fi
    sleep 0.1
    waited=$((waited + 1))
  done
}

ensure_port_free() {
  local port="$1"
  local label="$2"

  if lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    local pids
    pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN | tr '\n' ' ' | xargs)"

    if [[ -n "$pids" ]]; then
      echo "$label port $port is already in use."
      stop_processes "$label" $pids
    fi
  fi

  if lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Unable to free $label port $port. Stop the process manually or change the port." >&2
    exit 1
  fi
}

cleanup_frontend_next_dev() {
  local pid
  local next_pids
  local -a root_pids=()

  next_pids="$(
    {
      pgrep -f "$FRONTEND_DIR/node_modules/.bin/next dev" || true
      pgrep -f "next-server" || true
    } | dedupe_pids
  )"
  if [[ -n "$next_pids" ]]; then
    for pid in $next_pids; do
      root_pids+=("$pid")
    done
  fi

  if [[ -f "$FRONTEND_NEXT_LOCK" ]]; then
    pid="$(sed -n 's/.*"pid":\([0-9][0-9]*\).*/\1/p' "$FRONTEND_NEXT_LOCK" | head -n 1)"
    if [[ -n "$pid" ]]; then
      root_pids+=("$pid")
    fi
    rm -f "$FRONTEND_NEXT_LOCK"
  fi

  if [[ ${#root_pids[@]} -gt 0 ]]; then
    stop_processes "Frontend Next.js dev" "${root_pids[@]}"
  fi
}

ensure_env_file() {
  if [[ ! -f "$ENV_FILE" && -f "$ENV_EXAMPLE" ]]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    echo "Created .env from .env.example"
  fi

  if [[ -f "$ENV_FILE" && -f "$ENV_EXAMPLE" ]]; then
    local added_keys=0
    while IFS= read -r example_line; do
      [[ -z "$example_line" || "$example_line" == \#* ]] && continue
      local key="${example_line%%=*}"
      if ! grep -qE "^${key}=" "$ENV_FILE"; then
        printf '\n%s\n' "$example_line" >> "$ENV_FILE"
        added_keys=$((added_keys + 1))
      fi
    done < "$ENV_EXAMPLE"

    if [[ "$added_keys" -gt 0 ]]; then
      echo "Added $added_keys missing setting(s) to .env from .env.example"
    fi
  fi
}

ensure_backend_venv() {
  if [[ ! -d "$BACKEND_VENV" ]]; then
    echo "Creating backend virtual environment..."
    python3 -m venv "$BACKEND_VENV"
  fi
}

install_backend_deps() {
  if [[ "$INSTALL_DEPS" != "true" ]]; then
    return
  fi

  ensure_backend_venv

  if [[ ! -f "$BACKEND_STAMP" || "$BACKEND_DIR/requirements.txt" -nt "$BACKEND_STAMP" ]]; then
    echo "Installing backend dependencies..."
    (
      cd "$BACKEND_DIR"
      source .venv/bin/activate
      pip install -r requirements.txt
      touch "$BACKEND_STAMP"
    )
  fi
}

install_frontend_deps() {
  if [[ "$INSTALL_DEPS" != "true" ]]; then
    return
  fi

  if [[ ! -d "$FRONTEND_DIR/node_modules" || ! -f "$FRONTEND_STAMP" || "$FRONTEND_DIR/package-lock.json" -nt "$FRONTEND_STAMP" || "$FRONTEND_DIR/package.json" -nt "$FRONTEND_STAMP" ]]; then
    echo "Installing frontend dependencies..."
    (
      cd "$FRONTEND_DIR"
      npm install
      mkdir -p node_modules
      touch "$FRONTEND_STAMP"
    )
  fi
}

seed_backend() {
  if [[ "$SEED_DATA" != "true" ]]; then
    return
  fi

  echo "Seeding demo data..."
  (
    cd "$BACKEND_DIR"
    source .venv/bin/activate
    python seed.py
  )
}

cleanup() {
  local exit_code=$?

  if [[ -n "${BACKEND_PID:-}" ]]; then
    pkill -P "$BACKEND_PID" >/dev/null 2>&1 || true
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi

  if [[ -n "${FRONTEND_PID:-}" ]]; then
    pkill -P "$FRONTEND_PID" >/dev/null 2>&1 || true
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi

  wait >/dev/null 2>&1 || true
  exit "$exit_code"
}

run_local() {
  require_command python3
  require_command npm
  require_command lsof
  ensure_env_file
  install_backend_deps
  install_frontend_deps
  seed_backend
  cleanup_frontend_next_dev
  ensure_port_free "$BACKEND_PORT" "Backend"
  ensure_port_free "$FRONTEND_PORT" "Frontend"

  echo "Starting HireOS AI locally..."
  echo "Frontend: http://$HOST:$FRONTEND_PORT"
  echo "Backend:  http://$HOST:$BACKEND_PORT"
  echo "Login:    recruiter1@hireos.ai / Demo@123"
  echo

  (
    cd "$BACKEND_DIR"
    source .venv/bin/activate
    python -m uvicorn app.main:app --reload --host "$HOST" --port "$BACKEND_PORT" 2>&1 | sed 's/^/[backend] /'
  ) &
  BACKEND_PID=$!

  (
    cd "$FRONTEND_DIR"
    npm run dev -- --hostname "$HOST" --port "$FRONTEND_PORT" 2>&1 | sed 's/^/[frontend] /'
  ) &
  FRONTEND_PID=$!

  trap cleanup EXIT
  trap 'cleanup; exit 130' INT TERM

  while true; do
    if ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
      wait "$BACKEND_PID" || true
      break
    fi

    if ! kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
      wait "$FRONTEND_PID" || true
      break
    fi

    sleep 1
  done
}

run_docker() {
  require_command docker
  ensure_env_file
  echo "Starting HireOS AI with Docker Compose..."
  cd "$ROOT_DIR"
  docker compose up --build
}

if [[ "$USE_DOCKER" == "true" ]]; then
  run_docker
else
  run_local
fi

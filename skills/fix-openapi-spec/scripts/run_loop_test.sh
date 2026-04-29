#!/usr/bin/env bash

set -euo pipefail

SPECMATIC_DOCKER_IMAGE="${SPECMATIC_DOCKER_IMAGE:-specmatic/specmatic:latest}"
STARTUP_TIMEOUT_SECONDS=10
MAX_AUTO_PORT_ATTEMPTS=10
MAX_TEST_REQUEST_COMBINATIONS="${MAX_TEST_REQUEST_COMBINATIONS:-1}"
MOCK_PID=""
MOCK_CONTAINER_NAME=""
PORT=""
AUTO_PORT="true"
HEALTH_URL_OVERRIDE="${HEALTH_URL:-}"
TEST_BASE_URL_HOST="${TEST_BASE_URL_HOST:-host.docker.internal}"

usage() {
  cat <<EOF
Usage: $0 [--port <port>] <spec-file.[yaml|yml|json]>

Starts a Specmatic mock for the given spec, waits for the health endpoint,
and then runs a loop test against it.

Options:
  --port <port>  Run both mock and test against this port
  --help         Show this help message and exit
EOF
}

SPEC_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help)
      usage
      exit 0
      ;;
    --port)
      if [[ $# -lt 2 || "$2" == --* ]]; then
        echo "--port requires a value." >&2
        usage >&2
        exit 2
      fi
      PORT="$2"
      AUTO_PORT="false"
      shift 2
      ;;
    --*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      if [[ -n "${SPEC_FILE}" ]]; then
        echo "Only one spec file can be provided." >&2
        usage >&2
        exit 2
      fi
      SPEC_FILE="$1"
      shift
      ;;
  esac
done

if [[ -z "${SPEC_FILE}" ]]; then
  usage >&2
  exit 2
fi

if [[ ! -f "$SPEC_FILE" ]]; then
  echo "Spec file not found: $SPEC_FILE" >&2
  exit 2
fi

SPEC_DIR="$(cd "$(dirname "$SPEC_FILE")" && pwd -P)"
SPEC_BASENAME="$(basename "$SPEC_FILE")"

cleanup() {
  stop_mock
}

stop_mock() {
  if [[ -n "${MOCK_CONTAINER_NAME}" ]]; then
    docker stop "${MOCK_CONTAINER_NAME}" >/dev/null 2>&1 || true
    MOCK_CONTAINER_NAME=""
  fi

  if [[ -n "${MOCK_PID}" ]] && kill -0 "${MOCK_PID}" 2>/dev/null; then
    kill "${MOCK_PID}" 2>/dev/null || true
    wait "${MOCK_PID}" 2>/dev/null || true
  fi

  MOCK_PID=""
}

print_log_tail() {
  local label="$1"
  local file="$2"

  echo "Last lines from ${label} log (${file}):" >&2
  tail -n 40 "${file}" >&2 || true
}

trap cleanup EXIT

temp_dir() {
  local candidate

  for candidate in "${TMPDIR:-}" "${TEMP:-}" "${TMP:-}" "/tmp" "."; do
    if [[ -n "${candidate}" && -d "${candidate}" && -w "${candidate}" ]]; then
      echo "${candidate}"
      return 0
    fi
  done

  return 1
}

create_temp_log() {
  local prefix="$1"
  local base_dir

  base_dir="$(temp_dir)" || {
    echo "Could not find a writable temporary directory." >&2
    exit 2
  }

  mktemp "${base_dir%/}/specmatic-${prefix}.XXXXXX"
}

docker_preflight() {
  local info_output
  local active_context

  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is not installed or not on PATH." >&2
    exit 2
  fi

  if info_output="$(docker info 2>&1)"; then
    return 0
  fi

  active_context="$(docker context show 2>/dev/null || true)"

  if [[ "${active_context}" == desktop-* ]]; then
    echo "Docker Desktop is not available. Start Docker Desktop and retry." >&2
    echo "${info_output}" >&2
    exit 2
  fi

  echo "Docker daemon is not available. Start Docker and retry." >&2
  echo "${info_output}" >&2
  exit 2
}

docker_run_specmatic() {
  local command="$1"
  local specmatic_args=()
  shift

  if [[ "${command}" == "test" ]]; then
    specmatic_args+=(--testBaseURL "http://${TEST_BASE_URL_HOST}:${PORT}")
  fi

  docker run \
    --rm \
    --add-host "${TEST_BASE_URL_HOST}:host-gateway" \
    -v "${SPEC_DIR}:/usr/src/app" \
    -w /usr/src/app \
    "$@" \
    "${SPECMATIC_DOCKER_IMAGE}" \
    "${command}" \
    --port "${PORT}" \
    "${SPEC_BASENAME}" \
    --lenient \
    "${specmatic_args[@]}"
}

random_port() {
  echo $((49152 + RANDOM % 16384))
}

port_looks_available() {
  local port="$1"

  if (echo >"/dev/tcp/127.0.0.1/${port}") >/dev/null 2>&1; then
    return 1
  fi

  return 0
}

pick_port() {
  local candidate
  local attempt

  if [[ "${AUTO_PORT}" != "true" ]]; then
    return 0
  fi

  for ((attempt = 1; attempt <= 20; attempt++)); do
    candidate="$(random_port)"
    if port_looks_available "${candidate}"; then
      PORT="${candidate}"
      return 0
    fi
  done

  PORT="$(random_port)"
}

health_url() {
  if [[ -n "${HEALTH_URL_OVERRIDE}" ]]; then
    echo "${HEALTH_URL_OVERRIDE}"
    return 0
  fi

  echo "http://127.0.0.1:${PORT}/_specmatic/health"
}

mock_log_has_port_conflict() {
  grep -Eqi "Address already in use|BindException|EADDRINUSE|port is already allocated|Ports are not available|bind: address already in use" "${MOCK_LOG}" 2>/dev/null
}

http_status_code() {
  local url="$1"

  if command -v curl >/dev/null 2>&1; then
    curl -s -o /dev/null -w '%{http_code}' "${url}" || true
    return 0
  fi

  if command -v wget >/dev/null 2>&1; then
    wget -q -O /dev/null "${url}" >/dev/null 2>&1 && echo "200" || echo "000"
    return 0
  fi

  if command -v powershell >/dev/null 2>&1; then
    powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing -Uri '${url}' -Method Get -TimeoutSec 2).StatusCode } catch { 0 }" 2>/dev/null || true
    return 0
  fi

  if command -v pwsh >/dev/null 2>&1; then
    pwsh -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing -Uri '${url}' -Method Get -TimeoutSec 2).StatusCode } catch { 0 }" 2>/dev/null || true
    return 0
  fi

  echo "000"
}

MOCK_LOG="$(create_temp_log mock)"
TEST_LOG="$(create_temp_log test)"
MOCK_CONTAINER_NAME="specmatic-loop-mock-$(basename "${MOCK_LOG}")"

rm -rf "${SPEC_DIR}/build"

docker_preflight

mock_started="false"
for ((attempt = 1; attempt <= MAX_AUTO_PORT_ATTEMPTS; attempt++)); do
  pick_port
  echo "Using Specmatic port: ${PORT}"
  echo "Starting mock for ${SPEC_FILE}"

  docker run \
    --rm \
    -p "${PORT}:${PORT}" \
    --name "${MOCK_CONTAINER_NAME}" \
    -v "${SPEC_DIR}:/usr/src/app" \
    -w /usr/src/app \
    "${SPECMATIC_DOCKER_IMAGE}" \
    mock \
    --port "${PORT}" \
    "${SPEC_BASENAME}" \
    --lenient >"${MOCK_LOG}" 2>&1 &
  MOCK_PID=$!

  deadline=$((SECONDS + STARTUP_TIMEOUT_SECONDS))
  while (( SECONDS < deadline )); do
    if ! kill -0 "${MOCK_PID}" 2>/dev/null; then
      if [[ "${AUTO_PORT}" == "true" && "${attempt}" -lt "${MAX_AUTO_PORT_ATTEMPTS}" ]] && mock_log_has_port_conflict; then
        echo "Mock could not bind port ${PORT}; retrying with another port." >&2
        stop_mock
        continue 2
      fi

      echo "Mock exited before becoming healthy." >&2
      print_log_tail "mock" "${MOCK_LOG}"
      exit 1
    fi

    if [[ "$(http_status_code "$(health_url)")" == "200" ]]; then
      echo "Mock is healthy."
      mock_started="true"
      break
    fi

    sleep 1
  done

  if [[ "${mock_started}" == "true" ]]; then
    break
  fi

  if [[ "${AUTO_PORT}" == "true" && "${attempt}" -lt "${MAX_AUTO_PORT_ATTEMPTS}" ]] && mock_log_has_port_conflict; then
    echo "Mock did not become healthy on port ${PORT}; retrying with another port." >&2
    stop_mock
    continue
  fi

  echo "Mock did not become healthy within ${STARTUP_TIMEOUT_SECONDS} seconds." >&2
  print_log_tail "mock" "${MOCK_LOG}"
  exit 1
done

echo "Running loop test for ${SPEC_FILE}"
if ! docker_run_specmatic test -e "MAX_TEST_REQUEST_COMBINATIONS=${MAX_TEST_REQUEST_COMBINATIONS}" >"${TEST_LOG}" 2>&1; then
  stop_mock
  echo "Loop test failed." >&2
  print_log_tail "test" "${TEST_LOG}"
  exit 1
fi

stop_mock

echo "Loop test passed."
echo "Mock log: ${MOCK_LOG}"
echo "Test log: ${TEST_LOG}"

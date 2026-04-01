#!/usr/bin/env bash

set -euo pipefail

SPECMATIC_DOCKER_IMAGE="${SPECMATIC_DOCKER_IMAGE:-specmatic/specmatic:latest}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:9000/_specmatic/health}"
STARTUP_TIMEOUT_SECONDS=10
MAX_TEST_REQUEST_COMBINATIONS="${MAX_TEST_REQUEST_COMBINATIONS:-1}"
MOCK_PID=""
MOCK_CONTAINER_NAME=""

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <spec-file.[yaml|yml|json]>" >&2
  exit 2
fi

SPEC_FILE="$1"

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
  shift

  docker run \
    --rm \
    --network host \
    -v "${SPEC_DIR}:/usr/src/app" \
    -w /usr/src/app \
    "$@" \
    "${SPECMATIC_DOCKER_IMAGE}" \
    "${command}" \
    "${SPEC_BASENAME}" \
    --lenient
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

echo "Starting mock for ${SPEC_FILE}"
docker run \
  --rm \
  --network host \
  --name "${MOCK_CONTAINER_NAME}" \
  -v "${SPEC_DIR}:/usr/src/app" \
  -w /usr/src/app \
  "${SPECMATIC_DOCKER_IMAGE}" \
  mock \
  --lenient \
  "${SPEC_BASENAME}" >"${MOCK_LOG}" 2>&1 &
MOCK_PID=$!

deadline=$((SECONDS + STARTUP_TIMEOUT_SECONDS))
while (( SECONDS < deadline )); do
  if ! kill -0 "${MOCK_PID}" 2>/dev/null; then
    echo "Mock exited before becoming healthy." >&2
    print_log_tail "mock" "${MOCK_LOG}"
    exit 1
  fi

  if [[ "$(http_status_code "${HEALTH_URL}")" == "200" ]]; then
    echo "Mock is healthy."
    break
  fi

  sleep 1
done

if [[ "$(http_status_code "${HEALTH_URL}")" != "200" ]]; then
  echo "Mock did not become healthy within ${STARTUP_TIMEOUT_SECONDS} seconds." >&2
  print_log_tail "mock" "${MOCK_LOG}"
  exit 1
fi

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

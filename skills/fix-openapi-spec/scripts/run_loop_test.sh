#!/usr/bin/env bash

set -euo pipefail

USER_SPECIFIED_SPECMATIC_IMAGE="${SPECMATIC_DOCKER_IMAGE:-}"
SPECMATIC_DOCKER_IMAGE=""
PULL_SOURCE_IMAGE="specmatic/enterprise:latest"
STARTUP_TIMEOUT_SECONDS=10
MAX_AUTO_PORT_ATTEMPTS=10
MAX_TEST_REQUEST_COMBINATIONS="${MAX_TEST_REQUEST_COMBINATIONS:-1}"
MOCK_PID=""
MOCK_CONTAINER_NAME=""
PORT=""
AUTO_PORT="true"
HEALTH_URL_OVERRIDE="${HEALTH_URL:-}"
TEST_BASE_URL_HOST="${TEST_BASE_URL_HOST:-host.docker.internal}"
HOME_LICENSE_DIR="${HOME}/.specmatic"

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

# Source of truth: ../references/run-loop-test-image-selection.md
# Keep this implementation in sync with that reference and run_loop_test.ps1.
image_exists_locally() {
  local image="$1"
  docker image inspect "${image}" >/dev/null 2>&1
}

resolve_specmatic_image() {
  local candidate=""

  if [[ -n "${USER_SPECIFIED_SPECMATIC_IMAGE}" ]]; then
    candidate="${USER_SPECIFIED_SPECMATIC_IMAGE}"
  else
    candidate="$(docker image ls --format '{{.Repository}}:{{.Tag}}' | grep -i specmatic | grep -v '^<none>:<none>$' | head -n 1 || true)"
  fi

  if [[ -n "${candidate}" ]]; then
    if image_exists_locally "${candidate}"; then
      SPECMATIC_DOCKER_IMAGE="${candidate}"
      echo "Using local Specmatic image: ${SPECMATIC_DOCKER_IMAGE}"
      return 0
    fi

    if [[ -n "${USER_SPECIFIED_SPECMATIC_IMAGE}" ]]; then
      echo "**Action Required:** The provided Docker image does not exist locally: ${candidate}. Please provide a valid local image name." >&2
      return 1
    fi
  else
    echo "No local Docker image with 'specmatic' in its name was found. Trying to pull: ${PULL_SOURCE_IMAGE}"
  fi

  if docker pull "${PULL_SOURCE_IMAGE}"; then
    SPECMATIC_DOCKER_IMAGE="${PULL_SOURCE_IMAGE}"
    echo "Using Specmatic Enterprise image: ${SPECMATIC_DOCKER_IMAGE}"
    return 0
  fi

  echo "**Action Required:** I could not find a usable local Specmatic Enterprise image and pulling \`specmatic/enterprise:latest\` failed. Please pull the image yourself, then tell me the image name so I can continue the loop test." >&2
  return 1
}

generate_specmatic_config() {
  local test_base_url="http://${TEST_BASE_URL_HOST}:${PORT}"
  local mock_base_url="http://0.0.0.0:${PORT}"
  cat <<EOF
version: 3
systemUnderTest:
  service:
    definitions:
      - definition:
          source:
            filesystem:
              directory: .
          specs:
            - ${SPEC_BASENAME}
    runOptions:
      openapi:
        type: test
        baseUrl: ${test_base_url}
dependencies:
  services:
    - service:
        definitions:
          - definition:
              source:
                filesystem:
                  directory: .
              specs:
                - ${SPEC_BASENAME}
        runOptions:
          openapi:
            type: mock
            baseUrl: ${mock_base_url}
specmatic:
EOF

  cat <<EOF
  settings:
    test:
      schemaResiliencyTests: positiveOnly
      maxTestRequestCombinations: ${MAX_TEST_REQUEST_COMBINATIONS}
      lenientMode: true
    mock:
      lenientMode: true
EOF
}

docker_run_specmatic_with_config() {
  local command="$1"
  local docker_args=(
    run
    -i
    --entrypoint
    sh
    --add-host
    "${TEST_BASE_URL_HOST}:host-gateway"
    -v
    "${SPEC_DIR}:/usr/src/app"
    -w
    /usr/src/app
  )
  shift

  if [ -t 0 ]; then
    echo "Specmatic config must be piped into docker_run_specmatic_with_config." >&2
    exit 2
  fi

  if [[ -d "${HOME_LICENSE_DIR}" ]]; then
    docker_args+=(-v "${HOME_LICENSE_DIR}:/root/.specmatic")
  fi

  docker "${docker_args[@]}" \
    "$@" \
    "${SPECMATIC_DOCKER_IMAGE}" \
    -c "cat > /tmp/specmatic.yaml && specmatic ${command} --config /tmp/specmatic.yaml --lenient"
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
resolve_specmatic_image

mock_started="false"
for ((attempt = 1; attempt <= MAX_AUTO_PORT_ATTEMPTS; attempt++)); do
  pick_port
  echo "Using Specmatic port: ${PORT}"
  echo "Starting mock for ${SPEC_FILE}"

  generate_specmatic_config | docker_run_specmatic_with_config mock -p "${PORT}:${PORT}" --name "${MOCK_CONTAINER_NAME}" >"${MOCK_LOG}" 2>&1 &
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
if ! generate_specmatic_config | docker_run_specmatic_with_config test >"${TEST_LOG}" 2>&1; then
  stop_mock
  echo "Loop test failed." >&2
  print_log_tail "test" "${TEST_LOG}"
  exit 1
fi

stop_mock

echo "Loop test passed."
echo "Mock log: ${MOCK_LOG}"
echo "Test log: ${TEST_LOG}"

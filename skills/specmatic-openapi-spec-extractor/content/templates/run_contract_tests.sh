#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="${SCRIPT_DIR}"
SPECMATIC_DIR="${REPO_ROOT}/specmatic"
SPECMATIC_CONFIG="${REPO_ROOT}/specmatic.yaml"
REPORTS_DIR="${REPO_ROOT}/build/reports"
LOCAL_LICENSE_DIR="${REPO_ROOT}/.specmatic"
SPECMATIC_DOCKER_IMAGE="${SPECMATIC_DOCKER_IMAGE:-specmatic/enterprise:latest}"
SUT_PORT="${SUT_PORT:-<SUT_PORT>}"
PRE_TEST_SETUP_CMD="${PRE_TEST_SETUP_CMD:-}"
HOME_LICENSE_DIR="${HOME}/.specmatic"
LICENSE_FILE_NAME=""

find_license_file() {
  local candidate

  if [[ ! -d "${HOME_LICENSE_DIR}" ]]; then
    return 1
  fi

  for candidate in \
    "${HOME_LICENSE_DIR}/license.txt" \
    "${HOME_LICENSE_DIR}/license.lic" \
    "${HOME_LICENSE_DIR}/specmatic-license.txt" \
    "${HOME_LICENSE_DIR}/specmatic-license.lic"; do
    if [[ -f "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  candidate="$(find "${HOME_LICENSE_DIR}" -maxdepth 1 -type f \( \
    -iname '*license*' -o \
    -iname '*.lic' -o \
    -iname 'specmatic*.txt' \
  ) | head -n 1 || true)"

  if [[ -n "${candidate}" ]]; then
    printf '%s\n' "${candidate}"
    return 0
  fi

  return 1
}

prepare_license() {
  local source_license

  source_license="$(find_license_file || true)"
  if [[ -z "${source_license}" ]]; then
    return 0
  fi

  mkdir -p "${LOCAL_LICENSE_DIR}"
  LICENSE_FILE_NAME="$(basename "${source_license}")"
  cp "${source_license}" "${LOCAL_LICENSE_DIR}/${LICENSE_FILE_NAME}"
}

sync_specmatic_license_config() {
  local desired_path
  local temp_file

  [[ -n "${LICENSE_FILE_NAME}" ]] || return 0
  [[ -f "${SPECMATIC_CONFIG}" ]] || return 0

  desired_path="/usr/src/app/.specmatic/${LICENSE_FILE_NAME}"

  if grep -Fq "${desired_path}" "${SPECMATIC_CONFIG}"; then
    return 0
  fi

  if grep -Eq '^[[:space:]]*path:[[:space:]]*/usr/src/app/\.specmatic/' "${SPECMATIC_CONFIG}"; then
    perl -0pi -e "s#(^[ \t]*path:[ \t]*/usr/src/app/\\.specmatic/)[^\n]+#\${1}${LICENSE_FILE_NAME}#m" "${SPECMATIC_CONFIG}"
    return 0
  fi

  temp_file="$(mktemp)"
  awk -v license_path="${desired_path}" '
    {
      print $0
      if ($0 == "specmatic:") {
        print "  license:"
        print "    path: " license_path
      }
    }
  ' "${SPECMATIC_CONFIG}" >"${temp_file}"
  mv "${temp_file}" "${SPECMATIC_CONFIG}"
}

DOCKER_ARGS=(run --rm)
if [[ "$(uname -s)" == "Linux" ]]; then
  DOCKER_ARGS+=(--add-host host.docker.internal:host-gateway)
fi

mkdir -p "${REPORTS_DIR}"
prepare_license
sync_specmatic_license_config
resolve_enterprise_image

# Optional runtime throttle for slow or overly large suites.
# Add this only after you observe too many generated test combinations:
# yq -i '.specmatic.settings.test.maxTestRequestCombinations = 1' "${SPECMATIC_CONFIG}"

if [[ -n "${PRE_TEST_SETUP_CMD}" ]]; then
  echo "Running pre-test setup: ${PRE_TEST_SETUP_CMD}"
  (
    cd "${REPO_ROOT}"
    eval "${PRE_TEST_SETUP_CMD}"
  )
fi

VALIDATE_ARGS=(
  "${DOCKER_ARGS[@]}"
  -v "${REPO_ROOT}:/usr/src/app"
  -w /usr/src/app
)

TEST_ARGS=(
  "${DOCKER_ARGS[@]}"
  -v "${SPECMATIC_DIR}:/usr/src/app/specmatic"
  -v "${SPECMATIC_CONFIG}:/usr/src/app/specmatic.yaml"
  -v "${REPORTS_DIR}:/usr/src/app/build/reports"
  -w /usr/src/app
)

if [[ -n "${LICENSE_FILE_NAME}" ]]; then
  VALIDATE_ARGS+=(-v "${LOCAL_LICENSE_DIR}:/usr/src/app/.specmatic")
  TEST_ARGS+=(-v "${LOCAL_LICENSE_DIR}:/usr/src/app/.specmatic")
fi

docker "${VALIDATE_ARGS[@]}" \
  "${SPECMATIC_DOCKER_IMAGE}" \
  validate

docker "${TEST_ARGS[@]}" \
  "${SPECMATIC_DOCKER_IMAGE}" \
  test \
  --host=host.docker.internal \
  --port="${SUT_PORT}"

echo "Done. HTML report: ${REPORTS_DIR}/specmatic/html/index.html"

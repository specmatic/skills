#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="${SCRIPT_DIR}"
SPECMATIC_DIR="${REPO_ROOT}/specmatic"
SPECMATIC_CONFIG="${REPO_ROOT}/specmatic.yaml"
REPORTS_DIR="${REPO_ROOT}/build/reports"
USER_SPECIFIED_SPECMATIC_IMAGE="${SPECMATIC_DOCKER_IMAGE:-}"
SPECMATIC_DOCKER_IMAGE=""
SUT_PORT="${SUT_PORT:-<SUT_PORT>}"
PRE_TEST_SETUP_CMD="${PRE_TEST_SETUP_CMD:-}"
HOME_LICENSE_DIR="${HOME}/.specmatic"
PULL_SOURCE_IMAGE="specmatic/enterprise:latest"

image_exists_locally() {
  local image="$1"
  docker image inspect "${image}" >/dev/null 2>&1
}

find_latest_local_specmatic_image() {
  local repo=""
  local tag=""
  local id=""
  local created=""

  while IFS=$'\t' read -r repo tag id; do
    [[ -n "${repo}" && -n "${tag}" && -n "${id}" ]] || continue
    [[ "${repo}:${tag}" == "<none>:<none>" ]] && continue

    if [[ ! "${repo}" =~ [Ss][Pp][Ee][Cc][Mm][Aa][Tt][Ii][Cc] && ! "${tag}" =~ [Ss][Pp][Ee][Cc][Mm][Aa][Tt][Ii][Cc] ]]; then
      continue
    fi

    created="$(docker image inspect --format '{{.Created}}' "${id}" 2>/dev/null || true)"
    [[ -n "${created}" ]] || continue

    printf '%s\t%s:%s\n' "${created}" "${repo}" "${tag}"
  done < <(docker image ls --no-trunc --format '{{.Repository}}\t{{.Tag}}\t{{.ID}}') |
    sort -t $'\t' -k1,1r -k2,2 |
    head -n 1 |
    cut -f2
}

resolve_enterprise_image() {
  local candidate=""

  if [[ -n "${USER_SPECIFIED_SPECMATIC_IMAGE}" ]]; then
    candidate="${USER_SPECIFIED_SPECMATIC_IMAGE}"
  else
    candidate="$(find_latest_local_specmatic_image)"
  fi

  if [[ -n "${candidate}" ]]; then
    if image_exists_locally "${candidate}"; then
      SPECMATIC_DOCKER_IMAGE="${candidate}"
      echo "Using local Specmatic image: ${SPECMATIC_DOCKER_IMAGE}"
      return 0
    fi

    if [[ -n "${USER_SPECIFIED_SPECMATIC_IMAGE}" ]]; then
      echo "**Action Required:** The provided Docker image does not exist locally: ${candidate}. Please provide a valid local image name."
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

  echo "**Action Required:** I could not find a usable local Specmatic Enterprise image and pulling \`specmatic/enterprise:latest\` failed. Please pull the image yourself, then tell me the image name so I can continue the feedback loop."
  return 1
}

run_specmatic_command() {
  local docker_args_name="$1"
  shift

  local docker_args=()

  eval "docker_args=(\"\${${docker_args_name}[@]}\")"
  docker "${docker_args[@]}" "${SPECMATIC_DOCKER_IMAGE}" "$@"
}

DOCKER_ARGS=(run --rm)
if [[ "$(uname -s)" == "Linux" ]]; then
  DOCKER_ARGS+=(--add-host host.docker.internal:host-gateway)
fi

mkdir -p "${REPORTS_DIR}"
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

if [[ -d "${HOME_LICENSE_DIR}" ]]; then
  VALIDATE_ARGS+=(-v "${HOME_LICENSE_DIR}:/root/.specmatic:ro")
  TEST_ARGS+=(-v "${HOME_LICENSE_DIR}:/root/.specmatic:ro")
fi

run_specmatic_command VALIDATE_ARGS validate

run_specmatic_command TEST_ARGS \
  test \
  --host=host.docker.internal \
  --port="${SUT_PORT}"

echo "Done. HTML report: ${REPORTS_DIR}/specmatic/html/index.html"

#!/usr/bin/env bash

set -euo pipefail

USER_SPECIFIED_SPECMATIC_IMAGE="${SPECMATIC_DOCKER_IMAGE:-}"
SPECMATIC_DOCKER_IMAGE=""
PULL_SOURCE_IMAGE="specmatic/enterprise:latest"
HOME_LICENSE_DIR="${HOME}/.specmatic"

usage() {
  cat <<EOF
Usage: $0 <spec-file.[yaml|yml|json]>

Runs Specmatic validation for the given OpenAPI spec.

Options:
  --help    Show this help message and exit
EOF
}

if [[ $# -eq 1 && "$1" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 2
fi

SPEC_FILE="$1"

if [[ ! -f "$SPEC_FILE" ]]; then
  echo "Spec file not found: $SPEC_FILE" >&2
  exit 2
fi

SPEC_DIR="$(cd "$(dirname "$SPEC_FILE")" && pwd -P)"
SPEC_BASENAME="$(basename "$SPEC_FILE")"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not on PATH." >&2
  exit 2
fi

# Source of truth: ../references/validate-spec-image-selection.md
# Keep this implementation in sync with that reference and validate_spec.ps1.
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

resolve_specmatic_image() {
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

  echo "**Action Required:** I could not find a usable local Specmatic Enterprise image and pulling \`specmatic/enterprise:latest\` failed. Please pull the image yourself, then tell me the image name so I can continue validation." >&2
  return 1
}

docker_run_validate() {
  local docker_args=(
    run
    --rm
    --entrypoint
    sh
    -v
    "${SPEC_DIR}:/usr/src/app"
    -w
    /usr/src/app
  )

  if [[ -d "${HOME_LICENSE_DIR}" ]]; then
    docker_args+=(-v "${HOME_LICENSE_DIR}:/root/.specmatic")
  fi

  docker "${docker_args[@]}" \
    "${SPECMATIC_DOCKER_IMAGE}" \
    -c "specmatic validate --spec-file \"${SPEC_BASENAME}\""
}

resolve_specmatic_image

echo "Running validate for ${SPEC_FILE}"
docker_run_validate

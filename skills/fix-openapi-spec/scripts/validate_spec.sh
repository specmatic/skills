#!/usr/bin/env bash

set -euo pipefail

USER_SPECIFIED_SPECMATIC_IMAGE="${SPECMATIC_DOCKER_IMAGE:-}"
SPECMATIC_DOCKER_IMAGE=""
PULL_SOURCE_IMAGE="specmatic/enterprise:latest"
LOCAL_LICENSE_DIR=""
HOME_LICENSE_DIR="${HOME}/.specmatic"
LICENSE_FILE_NAME=""

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

  echo "**Action Required:** I could not find a usable local Specmatic Enterprise image and pulling \`specmatic/enterprise:latest\` failed. Please pull the image yourself, then tell me the image name so I can continue validation." >&2
  return 1
}

find_license_file() {
  local candidate

  if [[ ! -d "${HOME_LICENSE_DIR}" ]]; then
    return 1
  fi

  for candidate in \
    "${HOME_LICENSE_DIR}/specmatic-license.txt" \
    "${HOME_LICENSE_DIR}/license.json"; do
    if [[ -f "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  return 1
}

prepare_license() {
  local source_license

  source_license="$(find_license_file || true)"
  if [[ -z "${source_license}" ]]; then
    return 0
  fi

  LOCAL_LICENSE_DIR="${SPEC_DIR}/.specmatic"
  mkdir -p "${LOCAL_LICENSE_DIR}"
  LICENSE_FILE_NAME="$(basename "${source_license}")"
  cp -f "${source_license}" "${LOCAL_LICENSE_DIR}/${LICENSE_FILE_NAME}"
}

generate_validate_config() {
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
EOF

  if [[ -n "${LICENSE_FILE_NAME}" ]]; then
    cat <<EOF
specmatic:
  license:
    path: /usr/src/app/.specmatic/${LICENSE_FILE_NAME}
EOF
  fi
}

docker_run_validate_with_config() {
  local docker_args=(
    run
    --rm
    -i
    --entrypoint
    sh
    -v
    "${SPEC_DIR}:/usr/src/app"
    -w
    /usr/src/app
  )

  if [[ -n "${LICENSE_FILE_NAME}" ]]; then
    docker_args+=(-v "${LOCAL_LICENSE_DIR}:/usr/src/app/.specmatic")
  fi

  docker "${docker_args[@]}" \
    "${SPECMATIC_DOCKER_IMAGE}" \
    -c "cat > /tmp/specmatic.yaml && specmatic validate --config /tmp/specmatic.yaml"
}

resolve_specmatic_image
prepare_license

echo "Running validate for ${SPEC_FILE}"
generate_validate_config | docker_run_validate_with_config

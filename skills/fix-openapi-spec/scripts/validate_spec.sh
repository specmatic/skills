#!/usr/bin/env bash

set -euo pipefail

SPECMATIC_ENTERPRISE_DOCKER_IMAGE="${SPECMATIC_ENTERPRISE_DOCKER_IMAGE:-specmatic/enterprise:latest}"

usage() {
  cat <<EOF
Usage: $0 <spec-file.[yaml|yml|json]>

Runs Specmatic Enterprise validation for the given OpenAPI spec.

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

echo "Running enterprise validate for ${SPEC_FILE}"
docker run \
  --rm \
  -v "${SPEC_DIR}:/usr/src/app" \
  -w /usr/src/app \
  "${SPECMATIC_ENTERPRISE_DOCKER_IMAGE}" \
  validate \
  --spec-file \
  "${SPEC_BASENAME}"

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-$SCRIPT_DIR}"
CONFIG_PATH="$TARGET_DIR/specmatic.yaml"
REPORTS_DIR="$TARGET_DIR/reports"
SPECMATIC_IMAGE="${SPECMATIC_DOCKER_IMAGE:-specmatic/enterprise}"
TEMP_DIR="$(mktemp -d)"
LOCAL_BROKER_HOST="$(python3 - "$TARGET_DIR" <<'PY'
import json
import sys
from pathlib import Path

target = Path(sys.argv[1])
report_path = target / "extraction-report.json"
host = "localhost:9092"
if report_path.exists():
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        servers = report.get("diagnostics", {}).get("runtimeHints", {}).get("suggestedAsyncServers", [])
        if servers and servers[0].get("host"):
            host = servers[0]["host"]
    except Exception:
        pass
print(host)
PY
)"
APP_PORT="$(python3 - "$TARGET_DIR" <<'PY'
import sys
from pathlib import Path

target = Path(sys.argv[1])
port = "8080"
for candidate in sorted((target / "examples").rglob("*.json")):
    text = candidate.read_text(encoding="utf-8", errors="ignore")
    marker = "http://app:"
    if marker in text:
        port = text.split(marker, 1)[1].split('"', 1)[0].split("/", 1)[0]
        break
print(port)
PY
)"

cleanup() {
  rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Expected generated Specmatic config at $CONFIG_PATH" >&2
  exit 1
fi

mkdir -p "$REPORTS_DIR"
cp -R "$TARGET_DIR" "$TEMP_DIR/specmatic-run"
find "$TEMP_DIR/specmatic-run/examples" -name '*.json' -exec sed -i '' "s#http://app:${APP_PORT}#http://localhost:${APP_PORT}#g" {} + 2>/dev/null || \
find "$TEMP_DIR/specmatic-run/examples" -name '*.json' -exec sed -i "s#http://app:${APP_PORT}#http://localhost:${APP_PORT}#g" {} + 2>/dev/null || true
python3 - "$TEMP_DIR/specmatic-run/specmatic.yaml" "$LOCAL_BROKER_HOST" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
host = sys.argv[2]
text = path.read_text(encoding="utf-8")
updated = re.sub(r'host:\s*"kafka:29092"', f'host: "{host}"', text, count=1)
path.write_text(updated, encoding="utf-8")
PY

if command -v docker >/dev/null 2>&1; then
  docker run --rm \
    -v "$TEMP_DIR/specmatic-run:/workspace" \
    -w /workspace \
    "$SPECMATIC_IMAGE" \
    specmatic test --config /workspace/specmatic.yaml | tee "$REPORTS_DIR/specmatic-test.log"
  exit "${PIPESTATUS[0]}"
fi

echo "Docker is required to run generated async contract tests. Expected to execute with image '$SPECMATIC_IMAGE', but 'docker' was not found." >&2
exit 2

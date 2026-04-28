# Specmatic Deliverables and Acceptance

Use this guide when preparing the final runnable assets, acceptance checks, or troubleshooting notes for the contract-test workflow.

## Required Deliverables

At the end of the workflow, prepare:

- a runnable `run_contract_tests.sh` script for the full suite
- a `CONTRACT_TESTS_README.md`
- a final acceptance summary covering determinism, batching, and report generation

## `run_contract_tests.sh`

The final script should run the full suite in one go with no batch filters.

```bash
#!/bin/bash
set -euo pipefail

SUT_PORT=8090
PRE_TEST_SETUP_CMD="${PRE_TEST_SETUP_CMD:-}"

docker pull specmatic/enterprise:latest

# Optional runtime throttle for slow or overly large suites
# Add this only after you have observed that too many test combinations are being generated:
# yq -i '.specmatic.settings.test.maxTestRequestCombinations = 1' specmatic.yaml

if [ -n "$PRE_TEST_SETUP_CMD" ]; then
  echo "Running pre-test setup: $PRE_TEST_SETUP_CMD"
  eval "$PRE_TEST_SETUP_CMD"
fi

docker run --rm \
  -v "$(pwd)/specmatic:/usr/src/app/specmatic" \
  specmatic/enterprise examples validate \
  --spec-file "specmatic/<your-openapi-file.yaml>"

docker run --rm \
  --add-host host.docker.internal:host-gateway \
  -v "$(pwd)/specmatic:/usr/src/app/specmatic" \
  -v "$(pwd)/specmatic.yaml:/usr/src/app/specmatic.yaml" \
  -v "$(pwd)/build/reports:/usr/src/app/build/reports" \
  specmatic/enterprise test \
  --host=host.docker.internal \
  --port="$SUT_PORT"

echo "Done. HTML report: ./build/reports/specmatic/html/index.html"
```

Rules:

- The script must run the full suite without `--filter`.
- The script may include an optional deterministic setup hook.
- Do not hard-code `maxTestRequestCombinations` into the config by default.

## `CONTRACT_TESTS_README.md`

Document:

- what `run_contract_tests.sh` does step-by-step
- required inputs and files: `specmatic.yaml`, extracted specs, examples, running SUT, optional license file
- how to set `SUT_PORT`
- how to pass deterministic setup via `PRE_TEST_SETUP_CMD`
- where and when to tune `specmatic.settings.test.maxTestRequestCombinations`
- how to switch from full runs to filtered runs when needed
- known non-fixable failures

## Acceptance Checks

Verify all of the following:

1. Documentation consistency
- `SKILL.md` stays the control plane for the skill
- referenced config paths match schema-defined V3 paths

2. Determinism
- same batch + same seed inputs -> same examples and same pass/fail set
- different seed manifest -> examples update consistently without stale values

3. Batch loop behavior
- only current batch APIs are tested per run when filters are active
- the loop pauses after each batch and asks the user whether to continue
- after the batch loop completes, one final full-suite run happens without `--filter`
- runtime throttle guidance is applied only when suites are too large or too slow

4. Script contract
- `run_contract_tests.sh` runs the full suite in one command
- it validates examples, runs tests, and points to the report output

## Common Issues After Extraction

| Issue | Symptom | Fix |
|-------|---------|-----|
| Overly permissive schemas | Contract tests pass invalid payloads or miss regressions | Tighten request/response models in source code; avoid blanket `additionalProperties: true` unless intentional |
| Missing or weak response schemas | Response assertions are skipped or too generic | Add explicit response DTO or schema annotations and regenerate |
| Duplicate or missing `operationId` values | Ambiguous failures in reports and poor traceability | Ensure each operation has a stable, unique `operationId` |
| Missing auth metadata | Protected endpoints fail with 401 or 403 during tests | Add security schemes and required auth headers in test setup |
| Stub specs without concrete examples | Stub starts but returns unusable data or invalid responses | Add at least one concrete `examples` entry per stub response payload |
| Enum and nullability drift | Tests fail with enum or nullability mismatches | Align source annotations or validators with runtime behavior; use overlay only when source metadata cannot express it |

## What Not to Do

- Do not hand-write an OpenAPI spec when the framework can generate one.
- Do not edit the extracted OpenAPI file directly for iterative fixes.
- Do not modify business logic just to make contract tests pass.
- Do not add spec-rewrite scripts that preprocess generated OpenAPI to bypass mismatches.
- Do not mask mismatches with overly broad schemas unless the behavior is truly dynamic.
- Do not assume extraction captured everything; verify auth, error responses, headers, and downstream-dependent fields.
- Do not keep stale overlay patches after source annotations are fixed.

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `Cannot connect to the Docker daemon` | Docker Engine is not running | Start Docker Desktop or Engine, then rerun |
| Specmatic cannot reach the SUT | Wrong SUT port, SUT not started, or bind mismatch | Start the SUT first and verify `SUT_PORT` or `baseUrl` |
| `host.docker.internal` connectivity issues | Docker host alias not configured in that environment | Keep `--add-host host.docker.internal:host-gateway` or provide an equivalent mapping |
| Overlay changes are ignored | `overlayFilePath` not enabled or wrong path | Correct the runtime spec entry in `specmatic.yaml` |
| Stub returns invalid or empty responses | Stub spec lacks concrete examples or wrong port mapping | Add response examples and verify stub port mapping |
| `License file not found` or enterprise feature error | `specmatic.license.path` points to a missing file | Correct the path or remove `specmatic.license` and use the built-in trial license |
| Empty or minimal extracted spec | Routes not registered at import or startup time | Ensure all route modules are imported and the full router tree is loaded |
| Framework doc endpoint missing | OpenAPI library not configured or route path differs | Configure the framework’s OpenAPI support and verify the actual docs endpoint path |

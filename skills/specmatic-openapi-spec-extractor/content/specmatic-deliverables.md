# Specmatic Deliverables and Acceptance

Use this guide when preparing the final runnable assets, acceptance checks, or troubleshooting notes for the contract-test workflow.

## Required Deliverables

At the end of the workflow, prepare:

- a runnable `run_contract_tests.sh` script for the full suite
- a runnable `run_contract_tests.ps1` script for the full suite
- a `CONTRACT_TESTS_README.md`
- a final acceptance summary covering determinism, batching, and report generation

These deliverables are mandatory even when the application does not need any seed/setup step and even when Docker is not currently available to run the live Specmatic loop. In those cases, still generate the script and README with the setup hook left optional.

Execution rule:
- The generated script and the live hardening workflow must run Specmatic through the documented shell/Docker commands in this skill.
- Do not switch to Specmatic MCP execution in place of those commands.
- The checked-in templates under [content/templates/run_contract_tests.sh](content/templates/run_contract_tests.sh) and [content/templates/run_contract_tests.ps1](content/templates/run_contract_tests.ps1) are the source of truth for generated runner content.

## Runner Scripts

The final scripts should run the full suite in one go with no batch filters.
Use [content/templates/run_contract_tests.sh](content/templates/run_contract_tests.sh) for the canonical Bash template and [content/templates/run_contract_tests.ps1](content/templates/run_contract_tests.ps1) for the canonical PowerShell template.

Rules:

- Generate both `run_contract_tests.sh` and `run_contract_tests.ps1`.
- Both scripts must run the full suite without `--filter`.
- Both scripts must always be generated, even for simple applications with no database, fixtures, or in-memory seed flow.
- Both scripts may include an optional deterministic setup hook.
- Use the same logical interface in both scripts:
  - `SUT_PORT`
  - optional `PRE_TEST_SETUP_CMD`
  - optional `SPECMATIC_DOCKER_IMAGE`
- For simple applications, leave `PRE_TEST_SETUP_CMD` empty by default and do not invent a fake setup step.
- Do not hard-code `maxTestRequestCombinations` into the config by default.
- Both scripts must sniff for a license under the user home `.specmatic` directory, copy the discovered file into the current working directory under `./.specmatic/` when needed, and mount that directory into Docker.
- If a license is found, generated `specmatic.yaml` must include `specmatic.license.path: /usr/src/app/.specmatic/<license-file-name>`.
- If no license is found, omit `specmatic.license` entirely.
- Bash runner requirements:
  - resolve paths safely
  - add `--add-host host.docker.internal:host-gateway` only on Linux
  - avoid `--network host`
- PowerShell runner requirements:
  - resolve absolute paths before mounting
  - build Docker arguments with arrays
  - run optional setup with PowerShell execution
  - avoid `--network host`

## `CONTRACT_TESTS_README.md`

Document:

- what `run_contract_tests.sh` and `run_contract_tests.ps1` do step-by-step
- required inputs and files: `specmatic.yaml`, extracted specs, examples, running SUT, optional license file
- how to set `SUT_PORT`
- how to pass deterministic setup via `PRE_TEST_SETUP_CMD`
- that `PRE_TEST_SETUP_CMD` is optional and should remain unset for applications that do not require pre-test setup
- the supported networking model: host-run SUT on `host.docker.internal`
- that Linux runners add `--add-host host.docker.internal:host-gateway` and Windows/macOS do not
- that generated runners sniff `~/.specmatic` or the equivalent home `.specmatic` directory on Windows, copy any discovered license into the repo-local `./.specmatic/`, and mount it into Docker
- where and when to tune `specmatic.settings.test.maxTestRequestCombinations`
- how to switch from full runs to filtered runs when needed
- the minimal `PATH` filter syntax this skill supports for targeted runs:
  - `PATH='/users'`
  - `PATH='/users/*'`
  - `PATH='/users,/products'`
- how license-limited results are reported when no valid license is available:
  - total tests run
  - passed
  - failed
  - failed due to license limits
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
- `run_contract_tests.sh` and `run_contract_tests.ps1` run the full suite in one command
- they run `specmatic validate`, run tests, and point to the report output
- neither script uses `--network host`
- Linux runner adds `--add-host host.docker.internal:host-gateway`
- if a license is discovered, the runner copies it into `./.specmatic/`, mounts it into Docker, and `specmatic.yaml` targets `/usr/src/app/.specmatic/<license-file-name>`

5. License-limited completion
- if the user does not have a license, the workflow still produces deliverables
- the final report calls out how many tests failed due to license limits
- the final summary states that full hardening could not be completed because a valid license was not available

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
- Do not change implementation behavior, method signatures, returned values, control flow, persistence logic, or auth behavior just to make extraction or contract tests look better.
- Do not introduce DTO or model changes whose only purpose is to reshape the contract unless the user explicitly approves implementation changes.
- Do not add spec-rewrite scripts that preprocess generated OpenAPI to bypass mismatches.
- Do not mask mismatches with overly broad schemas unless the behavior is truly dynamic.
- Do not assume extraction captured everything; verify auth, error responses, headers, and downstream-dependent fields.
- Do not keep stale overlay patches after source annotations are fixed.

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `Cannot connect to the Docker daemon` | Docker Engine is not running | Start Docker Desktop or Engine, then rerun |
| Specmatic cannot reach the SUT | Wrong SUT port, SUT not started, or bind mismatch | Start the SUT first and verify `SUT_PORT` or `baseUrl` |
| `host.docker.internal` connectivity issues on Linux | Docker host alias not configured in that environment | Keep `--add-host host.docker.internal:host-gateway` in the Linux runner |
| `host.docker.internal` connectivity issues on Windows/macOS | SUT is not listening on the expected host port | Verify the SUT is running on the host and `SUT_PORT` matches |
| Overlay changes are ignored | `overlayFilePath` not enabled or wrong path | Correct the runtime spec entry in `specmatic.yaml` |
| Stub returns invalid or empty responses | Stub spec lacks concrete examples or wrong port mapping | Add response examples and verify stub port mapping |
| Trial-limit or enterprise-feature failure without a license | No valid license was available for all Specmatic test coverage | Report the license-limited failures, ask the user for a direct license path or a license under their home `.specmatic` directory, and continue to deliverables if no license is available |
| Empty or minimal extracted spec | Routes not registered at import or startup time | Ensure all route modules are imported and the full router tree is loaded |
| Framework doc endpoint missing | OpenAPI library not configured or route path differs | Configure the framework’s OpenAPI support and verify the actual docs endpoint path |

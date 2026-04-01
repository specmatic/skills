---
name: fix-openapi-spec
description: Use when asked to identify and fix errors in an OpenAPI spec that are preventing it from running as mock or test.
---

# Fix OpenAPI Spec

Use this skill when the task is to diagnose an OpenAPI spec that are preventing it from running as mock or test.

## Files

- Loop runner: `scripts/run_loop_test.sh`
- Loop runner (PowerShell): `scripts/run_loop_test.ps1`

## Workflow

1. Identify the input spec path.
2. Create a copy for edits named `<spec-file>-updated.<ext>` in the same directory as the source spec.
3. Create an append-only attempt log file named `<spec>_attempts.log.md` in the spec directory (`<spec>` means the spec filename without extension).
4. Run the loop test script against the editable copy and capture output.
5. Append a structured entry to `<spec>_attempts.log.md` for every loop-test run and fix attempt, including: what was attempted, why it was attempted, and whether it fixed the issue.
6. If the loop test passes, stop. There appears to be no obvious issue in the spec.
7. If the loop test fails, classify each reported error into one of the following:
   - `clear-actionable`: error message is clear, articulates a concrete spec problem, and preferably pinpoints where to fix.
   - `ambiguous`: error message is unclear, not sufficiently actionable, or appears clear but still causes loop-test halt after obvious fixes.
8. Do not spend iteration cycles fixing `clear-actionable` errors inside this skill run. List them out clearly for the user instead.
9. Focus fix attempts only on `ambiguous` errors, apply lawful fixes, rerun the loop test, and repeat until it passes or no lawful ambiguous-error fix remains.
10. If there are no lawful changes or workarounds left to suggest for ambiguous errors, ask the user to report the issue to the Specmatic team and stop.
11. Treat warnings that still allow mock startup and loop test pass as non-blocking unless the user asked for broader cleanup.

## Commands

Run the loop test with one of:

```bash
./.codex/skills/fix-openapi-spec/scripts/run_loop_test.sh path/to/spec-updated.yaml
```

```powershell
pwsh ./.codex/skills/fix-openapi-spec/scripts/run_loop_test.ps1 path/to/spec-updated.yaml
```

The script:

- runs Specmatic in Docker instead of relying on a host-installed `specmatic` binary
- uses `--network host` for both mock and test runs so both containers communicate with the same host network stack
- uses Docker options that work across Linux, macOS, and Windows (network mode + bind mount)
- passes `--lenient` to all Specmatic Docker command invocations
- bind-mounts the spec directory into `/usr/src/app` inside the container
- waits for `http://localhost:9000/_specmatic/health` to return `200` within 10 seconds
- runs the test step with `MAX_TEST_REQUEST_COMBINATIONS=1` by default
- exits `0` only when the mock came up and the test command passed
- reports a clear error if Docker is not installed or Docker Desktop / the Docker daemon is unavailable
- explicitly stops the mock container after the loop test concludes and uses trap-based cleanup as a fallback

## Manual Fallback

If the helper script fails for workflow or environment reasons rather than because of the spec itself, run the loop manually with Docker:

1. Start the mock with `docker run --rm --network host -v "<spec-dir>:/usr/src/app" -w /usr/src/app specmatic/specmatic:latest mock "<spec-file>" --lenient`
2. Wait for `http://localhost:9000/_specmatic/health` to return `200`
3. Run the bounded loop test with `docker run --rm --network host -e MAX_TEST_REQUEST_COMBINATIONS=1 -v "<spec-dir>:/usr/src/app" -w /usr/src/app specmatic/specmatic:latest test "<spec-file>" --lenient`
4. Explicitly stop the mock container after the test step and inspect the captured output

## Working Rules

- Always edit the `-updated` copy, not the original spec.
- Always maintain an append-only `<spec>_attempts.log.md` file and append an entry for each code/spec change and loop-test run.
- Every attempt log entry must include:
  - timestamp
  - attempted change or command
  - reason for the attempt
  - observed result
  - conclusion (`fixed`, `not fixed`, or `partially fixed`)
- Use the loop test output as the source of truth for the next fix.
- For each loop-test failure, classify each error as `clear-actionable` or `ambiguous`.
- `clear-actionable` means the message itself is sufficient for a user to fix the spec; these should be listed, not fixed, in this workflow.
- `ambiguous` means the message is unclear, non-pinpointed, contradictory, or appears clear but still causes loop-test halt after expected fixes.
- Any blocking error that still halts the loop test after seemingly unambiguous remediation must be reclassified as `ambiguous`.
- If the mock never becomes healthy within 10 seconds, treat that as a spec or startup failure and inspect the captured logs before changing the spec.
- Fix only blocking `ambiguous` failures first. Do not broaden the task into warning cleanup unless the user asked for it.

## Lawful Changes

- The following changes are not lawful and should not be suggested:
  - You cannot widen a JSON schema from `additionalProperties: false` to `additionalProperties: true`.
  - You cannot drop a property from a JSON schema completely. At most you may make properties optional or mandatory.
  - Descriptions, titles, summaries, and other metadata are never parsed by Specmatic. They should not be changed.

- Fixing regexes
  - If any error says that a value does not match its regex, fix the regex, not the value. However if the regex is valid, it's a bug in Specmatic and should be reported.
  - If the regex fix doesn't work, feel free to update the regex, or remove it to make it work. However if the initial regex was valid, create a bug report for the Specmatic team.

- When you find constraints to be contradictory (e.g. a string with `maxLength: 10` and `minLength: 20`), inform the user about the issue, offer to fix the spec, and provide options.

- Where errors seem valid (because the provided value indeed does not match the schema), elaborate on the error from Specmatic to the best of your understanding, and give examples of how the issue may be resolved by the user. Classify these as `clear-actionable` unless loop-test halt persists after applying the obvious remediation.

## Specmatic Bugs

- If the error message is not clear enough to identify the issue, or if the spec seems correct but a spec change was still required for the loop test to pass, create a bug report for the Specmatic team.
- Include all of the following in the bug report:
  - Error: the unclear or insufficient error message
  - Change: the change that had to be made to the spec in order for the loop test to pass
  - Sample spec: a simplistic sample spec that reproduces the issue
  - Logs: any relevant log snippet
  - Details: any other relevant details that can help the Specmatic team identify and fix the issue
- Show the user the bug report and ask the user to report it to the Specmatic team.
- As each such Specmatic issue report is produced, append it to a file named `errors-specmatic-<current-date>.md` in the current working directory. Create the file if it does not exist.

- When you stop working on the spec, if any issues were added to `errors-specmatic-<current-date>.md`, ask the user to review the file and send it to the Specmatic team.

- In your final response, state whether the loop test passed, name the updated spec file, mention any remaining non-blocking warnings you intentionally left unresolved, and include the Specmatic issue reports when the condition above applies.

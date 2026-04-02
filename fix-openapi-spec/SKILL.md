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
5. If the loop test passes, stop. There appears to be no obvious issue in the spec.
6. If the loop test fails, classify each reported error into one of the following:
   - `clear-actionable`: error message is clear, articulates a concrete spec problem, and preferably pinpoints where to fix.
   - `ambiguous`: error message is unclear, not sufficiently actionable, or appears clear but still causes loop-test halt after obvious fixes.
7. Append a structured entry to `<spec>_attempts.log.md` for every loop-test run and fix attempt, as soon as the fix attempt is made. Include: what was attempted, why it was attempted, and whether it fixed the issue.
8. Do not spend iteration cycles fixing `clear-actionable` errors inside this skill run. List them out clearly for the user instead.
9. Focus fix attempts only on `ambiguous` errors, apply lawful fixes, rerun the loop test, and repeat until it passes or no lawful ambiguous-error fix remains.
10. If there are no lawful changes or workarounds left to suggest for ambiguous errors, ask the user to report the issue to the Specmatic team and stop.
11. Treat warnings that still allow mock startup and loop test pass as non-blocking unless the user asked for broader cleanup.
12. After you have stopped (either because the loop test passed or because no lawful fix remains), if any issues were added to `raw-specmatic-issues-<current-date>.md`, create a new file named `specmatic-issues-<current-date>.md` that includes the de-duplicated issue reports. If there are multiple raw issues for the same problem, combine them into one issue in the user-friendly report and remove redundant information. But make sure that each issue in the new issues file contains the raw log snippets from the raw file.

Do not mention the mechanics of a loop test, lawful messages, etc to the user. Instead, the concluding message should contain the following details:
- If the loop test just passed, tell the user that you didn't see anything to fix.
- If you had to fix any issues to get the loop test to pass, report each fix, giving where the fix was applied, and what exactly was fixed.
- If the `specmatic-issues-<current-date>.md` file exists, tell the user that you found some issues to report the Specmatic team, and ask it to send the following files to the team: original unmodified spec, specmatic-issues-<current-date>.md, raw-specmatic-issues-<current-date>.md, <<spec_name>>_attempts.log.md.
- If there are any non-blocking warnings that you intentionally left unfixed, list them out clearly for the user, and ask the user if they want help fixing any of the issues.

## Commands

Run the loop test with one of:

```bash
./.codex/skills/fix-openapi-spec/scripts/run_loop_test.sh path/to/spec-updated.yaml
```

```powershell
pwsh ./.codex/skills/fix-openapi-spec/scripts/run_loop_test.ps1 path/to/spec-updated.yaml
```

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
- As soon as a Specmatic bug is identified, log the bug report in `raw-errors-specmatic-<current-date>.md`.

## Tips and Tricks

- The following changes are not lawful and should not be suggested:
  - You cannot widen a JSON schema from `additionalProperties: false` to `additionalProperties: true`.
  - You cannot drop a property from a JSON schema completely. At most you may make properties optional or mandatory.
  - Descriptions, titles, summaries, and other metadata are never parsed by Specmatic. They should not be changed.

- If any error says that a value does not match its regex, but the original regex appears valid, this is likely a Specmatic bug. Report the issue and ask the user to report it to the Specmatic team, but also try the following fixes in order:
  - First fix the regex, not the value, and re-attempt the loop test.
  - If the fix doesn't work, but based on the field name and schema context you can make an educated guess about how to update the regex, you may do so, and re-attempt the loop test.
  - If you can't find a way to provide a valid regex, remove it and re-attempt the loop test.
  - Note: Specmatic uses the dk.brics.automaton.Regexp library to generate regexes.

- When you find constraints to be contradictory (e.g. a string with `maxLength: 10` and `minLength: 20`), inform the user about the issue, offer to fix the spec, and provide options.

- Where errors seem valid (because the provided value indeed does not match the schema), elaborate on the error from Specmatic to the best of your understanding, and give examples of how the issue may be resolved by the user. Classify these as `clear-actionable` unless loop-test halt persists after applying the obvious remediation.

## Specmatic Bugs

- If the error message is not clear enough to identify the issue, or if the spec seems correct, but a spec change was still required for the count of "Successes" in the loop test report at the end to increase, create a bug report for the Specmatic team.
- Include all of the following in the bug report:
  - Error: the unclear or insufficient error message
  - Change: the change that had to be made to the spec in order for the loop test to pass
  - Logs: the relevant log snippet - include the raw log content
  - Details: any other relevant details that can help the Specmatic team identify and fix the issue
- As each such Specmatic issue report is produced, append it to a file named `raw-specmatic-issues-<current-date>.md` in the current working directory. Create the file if it does not exist.

- When you stop working on the spec, if any issues were added to `raw-specmatic-issues-<current-date>.md`, ask the user to review the file and send it to the Specmatic team.

- In your final response, state whether the loop test passed, name the updated spec file, mention any remaining non-blocking warnings you intentionally left unresolved, and include the Specmatic issue reports when the condition above applies.

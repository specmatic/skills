---
name: fix-openapi-spec
description: Use when asked to identify and fix errors in an OpenAPI specification that are preventing it from running as mock or test
---

# Fix OpenAPI Spec

Use this skill when the task is to diagnose an OpenAPI specification that are preventing it from running as mock or test.

## Workflow

Phase: Preparation

1. Identify the input spec path.
2. Create a copy for edits named `<spec-file>-updated.<ext>` in the same directory as the source spec.
    - Note: Always edit the `-updated` copy, not the original spec.
3. Create a single append-only attempt log file named `<spec>_attempts.log.md` in the spec directory (`<spec>` means the spec filename without extension).

Phase: Auto-fix debugging loop

1. Run the loop test script against the editable copy.
2. If the loop test passes, go to the next phase.
3. If the loop test fails, all tests that have failed are considered "must-fix" errors, and additionally an errors with obscure error messages that don't clearly indicate the issue in the spec are also considered "must-fix" errors.
4. For each must-fix error
    - form a hypothesis about the cause of the problem, and which allowed fix will resolve it
    - Apply the allowed fix
    - Append a structured entry to the `<spec>_attempts.log.md` file for every loop-test run and fix attempt, as soon as the fix attempt is made. Include: timestamp, attempted change, why it was attempted, and whether it fixed the issue, conclusion (`fixed`, `not fixed`)
    - Rerun the loop test, and repeat until it passes or no allowed fix to a must-fix error can be made.
    -  Create a "Specmatic Bug Report" as per "Specmatic Bug Report" section if:
      - The error message was opaque and did not clearly state the issue in the spec, OR
      - The spec seems correct, but a spec change was still required for the count of "Successes" in the loop test report at the end to increase, OR
      - There are no allowed changes or workarounds left to suggest for a must-fix error.
    - Create bug as and when seen, not all at the end.
5. Keep running this phase until either
  - all the must-fix errors have been fixed, or
  - remaining must-fix errors can conclusively NOT be fixed, as there no remaining allowed fixes for them.
6. Final check: once all the tests are passing, go back to step one and run the loop test again to make sure that there are no errors left.

Phase: Report on auto-fix phase

1. After you have stopped (either because the loop test passed or because no allowed fix remains), if any issues were added to `raw-specmatic-issues-<current-date>.md`, create a new file named `specmatic-issues-<current-date>.md` that includes the de-duplicated issue reports. If there are multiple raw issues for the same problem, combine them into one issue in the user-friendly report and remove redundant information. But make sure that each issue in the new issues file contains the raw log snippets from the raw file.
2. Prepare a report for the user. Do not mention the mechanics, such the fact that there was a test or mock, that anything passed or responded, etc to the user. Instead, the concluding message should contain the following details:
- If the loop test just passed, tell the user that you didn't see anything to fix.
- If you had to fix any issues to get the loop test to pass, report each fix with the following details:
  - where the fix was applied
  - what exactly was fixed
  - why did you have to fix it
  - whether it is an issue in the spec, or a bug in Specmatic
3. If the `specmatic-issues-<current-date>.md` file exists, tell the user that you found some issues to report the Specmatic team, and ask it to send the following files to the team: original unmodified spec, specmatic-issues-<current-date>.md, raw-specmatic-issues-<current-date>.md, <<spec_name>>_attempts.log.md.

Phase: Fix remaining "actionable" load time errors

- Run the validate command on the `<spec-file>-updated.<ext>` spec, and give the user a bullet-point list of all actionable load time errors, with the following details against each:
  - elaborate on the error to the best of your understanding
  - give a single concrete suggestion that would resolve the error
- Ask the user if they want help fixing any of the errors
- For each error the user wants help with, apply the allowed fix, and re-run the validate command until the error that the user wanted fixed is no longer appearing in the validate test report. If you believe that the error can't be fixed, create a Specmatic Bug Report for it.

## Allowed Fixes

- The following changes are not allowed:
  - Widening a JSON schema from `additionalProperties: false` to `additionalProperties: true`
  - Dropping a property from a JSON schema completely. At most you may make properties optional or mandatory
  - Changing descriptions, titles, summaries, and other metadata (these are never parsed by Specmatic)
  - Avoid changing the request or response datatype

- If you feel that an obscure must-fix error is related to a constraint (datatype is still correct but constraint such as regex, minLength, maximum, etc is broken), you may do the following:
  - First consider updating the constraint to correct it's syntax, and re-attempt the loop test.
  - If the fix doesn't work, but based on the field name and schema context you can make an educated guess about how to update the constraint, do so, and re-attempt the loop test.
  - If you can't find a way to provide a valid constraint, remove it and re-attempt the loop test.

- When an enum does not match the schema constraint, remove the constraint.
- When an example value does not match schema, update the example value to something meaningful based on the datatype and field name.

Note: for regexes, Specmatic uses the dk.brics.automaton.Regexp library, which supports a specific regex syntax.

## Specmatic Bug Report

- Log the bug report in `raw-specmatic-issues-<current-date>.md`
- Include all of the following in the bug report:
  - Error: the unclear or insufficient error message
  - Change: the change that had to be made to the spec in order for the loop test to pass
  - Logs: the relevant log snippet - include the raw log content
  - Details: any other relevant details that can help the Specmatic team identify and fix the issue
- As each such Specmatic issue report is produced, append it to a file named `raw-specmatic-issues-<current-date>.md` in the current working directory. Create the file if it does not exist.

## Available scripts

Run the loop test with one of:

```shell
[.codex|.agent]/skills/specmatic-skills/fix-openapi-spec/scripts/run_loop_test.sh <path/to/spec-updated.yaml>
```

```powershell
pwsh [.codex|.agent]/skills/specmatic-skills/fix-openapi-spec/scripts/run_loop_test.ps1 <path/to/spec-updated.yaml>
```

Validate the spec with one of:

```shell
[.codex|.agent]/skills/specmatic-skills/fix-openapi-spec/scripts/run_validate_test.sh <path/to/spec-updated.yaml>
```

```powershell
pwsh [.codex|.agent]/skills/specmatic-skills/fix-openapi-spec/scripts/run_validate_test.ps1 <path/to/spec-updated.yaml>
```

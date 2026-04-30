# Specmatic Feedback Loop

Use this guide only after the first OpenAPI extraction has succeeded and the spec has been saved.

## Entry Conditions

Before starting this loop:

- The spec has already been extracted and saved to the repo
- Obvious gaps in the generated contract have been inspected
- Source-level refinements have been attempted where safe
- The agent is ready to continue beyond extraction-only work

## Docker Execution Rule

Before running the Specmatic loop, assume Docker Engine is running and attempt the documented commands first.

Rules:

- Prefer OS-appropriate commands from this skill: Bash examples for macOS/Linux and PowerShell examples for Windows.
- Do not ask the user to confirm Docker availability before the first Specmatic `docker pull` or `docker run` attempt.
- If command output indicates a Docker-specific failure such as Docker not being installed, Docker not being on `PATH`, Docker Desktop not being available, or the Docker daemon / engine not running, stop and ask the user exactly:
  `**Action Required:** Please start the Docker engine, then confirm once it is running.`
- If no license is found, continue the loop with the built-in trial license.
- Treat any Specmatic trial-limit or enterprise-feature-limit hit as a licensing-caused test failure, not as a hard workflow blocker.
- If a Specmatic command fails for a trial-license or enterprise-feature limit reason, do not treat that as a hard blocker by itself.
- Call out that those failures are due to licensing, report how many tests ran, passed, failed, and failed due to license limits, and ask the user exactly:
  `**Action Required:** Some Specmatic tests failed because no valid license was available. If you have a license, please share its path or add it under your home .specmatic directory.`
- If the user shares a license path, configure `specmatic.yaml` to use it and mount it into Docker for the next run.
- If the user adds the license under their home `.specmatic` directory, use the existing auto-discovery flow on the next run.
- If the user does not have a license, continue to final reporting and deliverables, and state that full hardening could not be completed because of license-limited test failures.
- If the loop stops for a Docker-specific failure, still prepare the final runnable assets from this skill, including `run_contract_tests.sh`, `run_contract_tests.ps1`, and `CONTRACT_TESTS_README.md`
- State that the next blocked step is the Specmatic feedback loop only after a Docker command fails for a Docker-specific reason

## Default Behavior

- As soon as extraction and initial refinement succeed, move toward the Specmatic loop.
- Do not stop after extraction unless the user explicitly asked for extraction-only output.
- Do not wait for Docker confirmation before the first loop attempt.
- Run the Specmatic loop only through the shell/Docker commands documented in this skill.
- Do not use Specmatic MCP tools or any alternate Specmatic integration when this skill is active.

## Loop Sequence

Follow this sequence strictly:

`prepare Specmatic setup -> run validate -> run targeted tests -> fix mismatches -> repeat per batch -> final full run`

Execution rule:
- `prepare Specmatic setup`, `run validate`, `run targeted tests`, and `final full run` mean executing the documented `docker pull`, `docker run`, and shell commands from this skill.
- Do not replace those steps with Specmatic MCP calls.
- Use `host.docker.internal` as the supported default hostname for the host-run SUT.
- On Linux, add `--add-host host.docker.internal:host-gateway` to Specmatic `docker run` commands.
- On Windows/macOS, do not add extra host mapping.

## Batch Strategy

Do not test all APIs at once by default.

1. Discover API paths from the extracted spec.
2. Group paths by first segment such as `/orders`, `/users`, or `/invoices`.
3. List those groups to the user and ask which group(s) to harden first.
4. Run only the selected groups first.
5. After each batch, summarize progress and ask whether to move to the next batch.
6. After selected groups are done, run one final full Specmatic pass without any path filter.

For targeted batch runs in this skill, use only the `PATH` filter syntax:

- exact path: `PATH='/users'`
- subtree wildcard: `PATH='/users/*'`
- multiple paths in one filter: `PATH='/users,/products'`

Do not introduce other Specmatic filter fields in this skill unless the user explicitly asks for them.

## Required User Prompts

When the workflow needs a user decision, make the next step visually explicit. Prefix the prompt with `**Action Required:**` and then ask the exact question.
If the loop is blocked for any other reason that requires user action, use the same `**Action Required:**` prefix even when the exact prompt is not prewritten here.

- Before starting the hardening loop:
  `**Action Required:** I’ve finished extraction and initial refinement. I’m ready to start the Specmatic hardening loop. Do you want me to continue with the first API batch now?`
- Docker startup:
  `**Action Required:** Please start the Docker engine, then confirm once it is running.`
- Trial license limit:
  `**Action Required:** Some Specmatic tests failed because no valid license was available. If you have a license, please share its path or add it under your home .specmatic directory.`
- Initial selection:
  `**Action Required:** I found these API groups from the spec: <list>. Which group(s) do you want to harden first?`
- Long-running batch:
  `**Action Required:** This batch is taking longer than expected. Do you want to continue this batch, or defer it and move to the next batch?`
- Next batch:
  `**Action Required:** Do you want to move to the next batch of APIs from the remaining list?`

## Fix Order

Always apply fixes in this order:

1. Source annotations/decorators/config
2. OpenAPI overlay
3. Specmatic stubs and stub examples

Rules:

- Always attempt source-level fixes first.
- Source-level fixes for this skill mean extraction-related annotations, decorators, comments, and non-behavioral config only.
- Use overlay only when source metadata cannot express the required contract.
- Do not change implementation behavior or method signatures as part of the fix loop unless the user explicitly asks for implementation changes.
- If a mismatch cannot be fixed via source metadata or overlay, classify it as non-fixable and report it.
- Do not create spec-rewrite scripts that mutate the generated OpenAPI as a workaround.

## Runtime Throttle Rule

Do not set `specmatic.settings.test.maxTestRequestCombinations` by default.

Add it only when:

- too many contract tests are being generated, or
- the suite is taking too long to run

When throttling is needed:

- add `maxTestRequestCombinations` as a temporary runtime throttle
- use `1` as a strong throttle when necessary
- remove or increase it later for broader coverage

## Batch Progress Reporting

After each batch, report:

- `Batch`
- `Filter`
- `Duration`
- `Passed`
- `Failed (fixable)`
- `Failed (non-fixable)`
- `Failed (license-limited)` when applicable
- `Remaining batches`
- `Deferred batches`

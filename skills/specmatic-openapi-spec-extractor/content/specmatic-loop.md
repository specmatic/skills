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
  `Please confirm if docker engine is running`
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

- Initial selection:
  `I found these API groups from the spec: <list>. Which group(s) do you want to harden first?`
- Long-running batch:
  `This batch is taking longer than expected. Do you want to continue this batch, or defer it and move to the next batch?`
- Next batch:
  `Do you want to move to the next batch of APIs from the remaining list?`

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
- `Remaining batches`
- `Deferred batches`

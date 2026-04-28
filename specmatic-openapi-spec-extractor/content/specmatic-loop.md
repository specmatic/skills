# Specmatic Feedback Loop

Use this guide only after the first OpenAPI extraction has succeeded and the spec has been saved.

## Entry Conditions

Before starting this loop:

- The spec has already been extracted and saved to the repo
- Obvious gaps in the generated contract have been inspected
- Source-level refinements have been attempted where safe
- The agent is ready to continue beyond extraction-only work

## Docker Confirmation Rule

Before running the Specmatic loop, explicitly ask the user to confirm Docker Engine is running.

Use this exact style:

- `Next, we will harden the extracted OpenAPI spec using the Specmatic feedback loop. Please confirm Docker Engine is running, and I’ll begin the setup.`

If Docker is not confirmed yet:

- Stop after reporting that extraction and refinement are done
- State that the next blocked step is the Specmatic feedback loop

## Default Behavior

- As soon as extraction and initial refinement succeed, move toward the Specmatic loop.
- Do not stop after extraction unless the user explicitly asked for extraction-only output.
- Do not enter the Docker-dependent loop before the Docker confirmation above.

## Loop Sequence

Follow this sequence strictly:

`confirm Docker -> prepare Specmatic setup -> validate examples -> run targeted tests -> fix mismatches -> repeat per batch -> final full run`

## Batch Strategy

Do not test all APIs at once by default.

1. Discover API paths from the extracted spec.
2. Group paths by first segment such as `/orders`, `/users`, or `/invoices`.
3. List those groups to the user and ask which group(s) to harden first.
4. Run only the selected groups first.
5. After each batch, summarize progress and ask whether to move to the next batch.
6. After selected groups are done, run one final full Specmatic pass without any path filter.

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
- Use overlay only when source metadata cannot express the required contract.
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

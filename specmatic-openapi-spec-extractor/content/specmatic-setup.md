# Specmatic Setup

Use this guide when preparing `specmatic.yaml`, overlays, external examples, or deterministic setup needed for the contract-test loop.

## Setup Sequence

Follow this sequence:

`pull image -> create schema-valid config -> configure examples/overlay -> add deterministic setup -> validate examples`

## Pull Image

Always pull the latest image before starting Specmatic contract tests or stubs:

```bash
docker pull specmatic/enterprise:latest
```

## `specmatic.yaml` Shape

Schema reference:

- `https://github.com/specmatic/schemastore/blob/master/src/schemas/json/specmatic.json`

Validate config before first test run and after config edits:

```bash
npx --yes ajv-cli validate \
  -s https://raw.githubusercontent.com/specmatic/schemastore/master/src/schemas/json/specmatic.json \
  -d specmatic.yaml
```

## Field Placement Map

| YAML path | Purpose |
|---|---|
| `systemUnderTest.service.definitions` | Contract source and list of specs under test |
| `systemUnderTest.service.runOptions.openapi` | Test runtime options including `type`, `baseUrl`, and per-spec filters |
| `systemUnderTest.service.runOptions.openapi.specs[].spec.overlayFilePath` | Overlay file to apply when source annotations cannot express the needed contract |
| `systemUnderTest.service.data.examples` | External examples configuration |
| `systemUnderTest.service.data.dictionary` | Dictionary path when substitutions are required |
| `specmatic.settings.test.schemaResiliencyTests` | Schema resiliency coverage control |
| `specmatic.settings.test.maxTestRequestCombinations` | Optional runtime throttle for oversized or slow suites |

## Baseline Config Template

```yaml
version: 3
systemUnderTest:
  service:
    definitions:
      - definition:
          source:
            filesystem:
              directory: ./specmatic
          specs:
            - spec:
                id: <your-api-id>
                path: <your-openapi-file.yaml>
    runOptions:
      openapi:
        type: test
        baseUrl: http://host.docker.internal:<SUT_PORT>
        specs:
          - spec:
              id: <your-api-id>
              # overlayFilePath: ./specmatic/openapi.overlay.yaml
              # filter: PATH!='/internal/metrics'
    data:
      examples:
        - directories:
            - ./specmatic/<your-openapi-file_without_ext>_examples
            - ./specmatic/stub-<dependency-name>_examples
      # dictionary:
      #   path: ./specmatic/dictionary.yaml
specmatic:
  settings:
    test:
      schemaResiliencyTests: all
  governance:
    report:
      formats:
        - html
      outputDirectory: ./build/reports/specmatic
```

## Config Rules

- Always set `specmatic.settings.test.schemaResiliencyTests: all`.
- Do not add `specmatic.settings.test.maxTestRequestCombinations` by default.
- Add `maxTestRequestCombinations` only when too many tests are being generated or runtime is too high.
- Configure `specmatic.license.path` only if the license file is actually present.
- If the license file is absent, omit `specmatic.license` entirely and let Specmatic use its built-in trial license.
- Do not fail the workflow only because the enterprise license file is missing.
- Treat any config key outside schema as invalid.

## Overlay Rules

When an overlay is needed, enable it under the runtime spec entry:

```yaml
systemUnderTest:
  service:
    runOptions:
      openapi:
        specs:
          - spec:
              id: <your-api-id>
              overlayFilePath: ./specmatic/openapi.overlay.yaml
```

Rules:

- Set `overlayFilePath` under `systemUnderTest.service.runOptions.openapi.specs[].spec`.
- Use a repo-relative path.
- If multiple specs are tested, set `overlayFilePath` for each spec entry that needs it.

## External Examples

Directory conventions:

- Main API spec: `./specmatic/<spec-name>_examples/`
- Stub specs: `./specmatic/stub-<dependency-name>_examples/`

Rules:

- Regenerate or update examples for each batch so payloads match the deterministic data for that run.
- Do not add examples for `400` scenarios. Let Specmatic generate invalid-request coverage through schema resiliency tests.

Validate external examples before running tests:

```bash
docker run --rm \
  -v "$(pwd)/specmatic:/usr/src/app/specmatic" \
  specmatic/enterprise examples validate \
  --spec-file "specmatic/<your-openapi-file.yaml>"
```

If examples are in non-default locations:

```bash
docker run --rm \
  -v "$(pwd):/usr/src/app" \
  specmatic/enterprise examples validate \
  --spec-file "specmatic/<your-openapi-file.yaml>" \
  --examples-dir "<custom-examples-dir>"
```

## Deterministic Data-Prep Expectations

Before each batch, use a deterministic data-prep command or script that:

- resets or creates deterministic dummy data in the SUT data store
- emits a run manifest such as `./build/specmatic/run-manifest.json`
- rewrites or templates example payloads from that manifest

Expected outcome:

- same batch + same seed inputs -> same examples and same pass/fail set
- changed manifest -> examples update consistently without stale IDs

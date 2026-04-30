# Specmatic Setup

Use this guide when preparing `specmatic.yaml`, overlays, external examples, or deterministic setup needed for the contract-test loop.

## Setup Sequence

Follow this sequence:

`pull image -> create schema-valid config -> configure examples/overlay -> add deterministic setup -> run validate`

## Pull Image

Always pull the latest image before starting Specmatic contract tests or stubs:

```bash
docker pull specmatic/enterprise:latest
```

```powershell
docker pull specmatic/enterprise:latest
```

Execution rule:
- Use shell/Docker commands exactly as documented in this skill for validation, stubs, and test execution.
- Do not use Specmatic MCP tools as a substitute for these commands.
- Prefer OS-appropriate commands: Bash on macOS/Linux and PowerShell on Windows.

## `specmatic.yaml` Shape

Schema reference:

- `https://github.com/specmatic/schemastore/blob/master/src/schemas/json/specmatic.json`

Validate config before first test run and after config edits:

```bash
npx --yes ajv-cli validate \
  -s https://raw.githubusercontent.com/specmatic/schemastore/master/src/schemas/json/specmatic.json \
  -d specmatic.yaml
```

```powershell
npx --yes ajv-cli validate `
  -s https://raw.githubusercontent.com/specmatic/schemastore/master/src/schemas/json/specmatic.json `
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
  # license:
  #   path: /usr/src/app/.specmatic/<license-file-name>
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
- When present, point `specmatic.license.path` at the in-container path `/usr/src/app/.specmatic/<license-file-name>`.
- License discovery source is the user home `.specmatic` directory:
  - macOS/Linux: `~/.specmatic`
  - Windows: `$HOME/.specmatic` or `%USERPROFILE%\\.specmatic`
- Generated runners should sniff that directory, copy the discovered license into the current working directory under `./.specmatic/` when needed, and mount that directory into Docker.
- When a license is discovered, generated runners must also sync `specmatic.yaml` so `specmatic.license.path` points at `/usr/src/app/.specmatic/<license-file-name>` before running Specmatic.
- If the license file is absent, omit `specmatic.license` entirely and let Specmatic use its built-in trial license.
- If the license file is absent, do not stop the loop up front. Continue with the built-in trial.
- If a later Specmatic command fails because of a trial-license or enterprise-feature limit, ask the user for either:
  - a direct license file path, or
  - a license placed under their home `.specmatic` directory
- If the user shares a direct path, configure `specmatic.yaml` to point at the mounted in-container location for that file and mount it into Docker for the rerun.
- Do not fail the workflow only because the enterprise license file is missing.
- Treat any config key outside schema as invalid.
- Default supported topology: host-run SUT only. Containerized-SUT and Docker Compose networking are out of scope for this iteration.
- Keep `baseUrl` on `http://host.docker.internal:<SUT_PORT>` for Windows, macOS, and Linux.

## Docker Networking Note

- Docker Desktop on Windows and macOS already resolves `host.docker.internal` for containers.
- Linux typically does not, so Specmatic `docker run` commands must add `--add-host host.docker.internal:host-gateway`.
- Do not use `--network host` for this skill.

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

## PATH Filter Rule

This skill only needs the minimal `PATH` filter syntax for targeted contract-test batches.

- Configure it under `systemUnderTest.service.runOptions.openapi.specs[].spec.filter`.
- Exact path: `PATH='/users'`
- Subtree wildcard: `PATH='/users/*'`
- Multiple paths in one filter: `PATH='/users,/products'`
- Remove the filter entirely for the final full-suite run.

## External Examples

Directory conventions:

- Main API spec: `./specmatic/<spec-name>_examples/`
- Stub specs: `./specmatic/stub-<dependency-name>_examples/`

Rules:

- Regenerate or update examples for each batch so payloads match the deterministic data for that run.
- Do not add examples for `400` scenarios. Let Specmatic generate invalid-request coverage through schema resiliency tests.
- Use [content/specmatic-external-example.schema.json](content/specmatic-external-example.schema.json) as the source of truth for example file structure.

## Downstream Stub Setup

If the SUT depends on one or more other HTTP APIs during contract tests, use a Specmatic stub for each required dependency on the exact host port expected by the SUT.

Directory conventions:

- dependency contract: `./specmatic/<dependency-name>.yaml`
- stub examples: `./specmatic/stub-<dependency-name>_examples/`

Example stub startup commands.

macOS/Linux:

```bash
docker run --rm \
  -p 8090:8090 \
  -v "$(pwd):/usr/src/app" \
  -w /usr/src/app \
  specmatic/enterprise:latest stub \
  --host=0.0.0.0 \
  --port=8090 \
  "specmatic/<dependency-name>.yaml"
```

Windows PowerShell:

```powershell
docker run --rm `
  -p 8090:8090 `
  -v "${PWD}:/usr/src/app" `
  -w /usr/src/app `
  specmatic/enterprise:latest stub `
  --host=0.0.0.0 `
  --port=8090 `
  "specmatic/<dependency-name>.yaml"
```

Rules:

- Repeat this setup for each downstream dependency needed by the current batch.
- Match the exact dependency port the SUT is trying to call for each dependency, for example `8090`, `8091`, or another fixed port.
- Generate concrete stub examples for the downstream success paths the SUT needs from each dependency.
- Use stub examples to model required downstream state before rerunning the batch.
- If the final runner needs to start multiple dependency stubs automatically, wire that into `PRE_TEST_SETUP_CMD`.

## External Example Structure

Generate each external example file as a single JSON object that matches [content/specmatic-external-example.schema.json](content/specmatic-external-example.schema.json).

Standard example shape:

```json
{
  "http-request": {
    "method": "POST",
    "path": "/users",
    "headers": {
      "Content-Type": "application/json"
    },
    "body": {
      "name": "Jane"
    }
  },
  "http-response": {
    "status": 201,
    "headers": {
      "Content-Type": "application/json"
    },
    "body": {
      "id": 10,
      "name": "Jane"
    }
  },
  "name": "create user success"
}
```

Partial example shape:

```json
{
  "partial": {
    "http-request": {
      "method": "GET",
      "path": "/users/10"
    },
    "http-response": {
      "status": 200,
      "body": {
        "id": 10
      }
    }
  },
  "name": "get user partial"
}
```

Generation rules:

- `http-request` and `http-response` are required for standard examples.
- `partial` is required for partial examples, and its nested object must contain `http-request` and `http-response`.
- `http-request.method` is required.
- `http-response.status` is required.
- `http-request.body` and `http-response.body` may be any valid JSON value.
- `headers` maps use string values.
- `query` is a JSON object keyed by query parameter name.
- `form-fields` is a JSON object keyed by form field name.
- `multipart-formdata` entries must use either:
  - `name` + `content`
  - `name` + `filename`
- `bodyRegex` belongs inside `http-request`.
- Optional top-level metadata supported by the parser includes:
  - `name`
  - `transient`
  - `delay-in-seconds`
  - `delay-in-milliseconds`
  - `http-stub-id`
  - `id`
- Additional top-level keys are allowed and should be treated as example data fields carried alongside the request/response pair.

Run `specmatic validate` before running tests so Specmatic validates the discovered specifications and examples together from the mounted workspace.
This is only a preflight step. A successful `validate` run does not complete the skill; it must be followed by `specmatic test` against the running SUT.

macOS:

```bash
docker run --rm \
  -v "$(pwd):/usr/src/app" \
  -v "$(pwd)/.specmatic:/usr/src/app/.specmatic" \
  -w /usr/src/app \
  specmatic/enterprise:latest validate
```

Linux:

```bash
docker run --rm \
  --add-host host.docker.internal:host-gateway \
  -v "$(pwd):/usr/src/app" \
  -v "$(pwd)/.specmatic:/usr/src/app/.specmatic" \
  -w /usr/src/app \
  specmatic/enterprise:latest validate
```

Windows PowerShell:

```powershell
docker run --rm `
  -v "${PWD}:/usr/src/app" `
  -v "${PWD}/.specmatic:/usr/src/app/.specmatic" `
  -w /usr/src/app `
  specmatic/enterprise:latest validate
```

If examples are in non-default locations, ensure `specmatic.yaml` references those directories correctly before running `validate`. The same `validate` command should still be used; do not switch back to `examples validate`.

Full contract test command.

macOS:

```bash
docker run --rm \
  -v "$(pwd)/specmatic:/usr/src/app/specmatic" \
  -v "$(pwd)/.specmatic:/usr/src/app/.specmatic" \
  -v "$(pwd)/specmatic.yaml:/usr/src/app/specmatic.yaml" \
  -v "$(pwd)/build/reports:/usr/src/app/build/reports" \
  specmatic/enterprise:latest test \
  --host=host.docker.internal \
  --port="<SUT_PORT>"
```

Linux:

```bash
docker run --rm \
  --add-host host.docker.internal:host-gateway \
  -v "$(pwd)/specmatic:/usr/src/app/specmatic" \
  -v "$(pwd)/.specmatic:/usr/src/app/.specmatic" \
  -v "$(pwd)/specmatic.yaml:/usr/src/app/specmatic.yaml" \
  -v "$(pwd)/build/reports:/usr/src/app/build/reports" \
  specmatic/enterprise:latest test \
  --host=host.docker.internal \
  --port="<SUT_PORT>"
```

Windows PowerShell:

```powershell
docker run --rm `
  -v "${PWD}/specmatic:/usr/src/app/specmatic" `
  -v "${PWD}/.specmatic:/usr/src/app/.specmatic" `
  -v "${PWD}/specmatic.yaml:/usr/src/app/specmatic.yaml" `
  -v "${PWD}/build/reports:/usr/src/app/build/reports" `
  specmatic/enterprise:latest test `
  --host=host.docker.internal `
  --port="<SUT_PORT>"
```

## Deterministic Data-Prep Expectations

Before each batch, use a deterministic data-prep command or script that:

- resets or creates deterministic dummy data in the SUT data store
- emits a run manifest such as `./build/specmatic/run-manifest.json`
- rewrites or templates example payloads from that manifest

Expected outcome:

- same batch + same seed inputs -> same examples and same pass/fail set
- changed manifest -> examples update consistently without stale IDs

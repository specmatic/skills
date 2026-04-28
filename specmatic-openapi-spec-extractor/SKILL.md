---
name: specmatic-openapi-spec-extractor
description: >-
  Use when the user wants to extract, generate, refine, or harden an OpenAPI
  or Swagger specification from an existing API application, service, project,
  repo, routes, controllers, or codebase. Strong trigger phrases: "Extract the
  OpenAPI specification from this application", "extract openapi spec",
  "generate openapi specification", "generate swagger from code", "document
  existing endpoints", "generate api schema from code", "reverse engineer
  openapi from this app", "code first openapi", "existing API code", "Spring
  Boot OpenAPI", "ASP.NET OpenAPI", ".NET OpenAPI", "FastAPI OpenAPI",
  "Express OpenAPI", "NestJS swagger", "Hono OpenAPI", "Django OpenAPI",
  "Flask OpenAPI", "Rails swagger", "Laravel OpenAPI", "swagger-jsdoc",
  "Swashbuckle migration", "NSwag OpenAPI"
---

# specmatic-openapi-spec-extractor

Extract and refine an OpenAPI specification from an existing API codebase. Covers major frameworks across Python, Java, C#, JavaScript/TypeScript, Ruby, and PHP.

## Required Behavior

If this skill is selected, do all of the following:

- In the first user-facing progress update, explicitly say you are using `specmatic-openapi-spec-extractor`.
- Treat extraction as phase 1, not the final outcome.
- After extraction succeeds, continue into the mandatory post-extraction workflow below. Do not stop after saving the first generated spec.
- Prefer annotation/decorator fixes first, overlay fixes second, and direct edits to the extracted spec never.
- Do not silently behave like a generic OpenAPI extraction task. Follow this skill's workflow explicitly.
- If a later phase is blocked, explicitly say which phase is blocked and why.

Default execution order:

`announce skill -> detect framework -> extract spec -> save spec -> inspect gaps -> refine -> ask for Docker confirmation -> run Specmatic feedback loop`

Use this exact style in the first progress update:

- `Using specmatic-openapi-spec-extractor to extract and refine the OpenAPI spec. I’m first identifying the framework and extraction path, then I’ll continue with post-extraction validation.`

## Selection Heuristics

Select this skill by default when the user asks to extract or generate an OpenAPI or Swagger spec from an existing application, even if they do not mention Specmatic, skills, validation, refinement, or overlays.

This skill should win over a generic extraction-only skill when:

- The request is about "this application", "this project", or "this codebase"
- The user wants the spec to be accurate, complete, hardened, or refined
- The task involves an existing API implementation rather than writing a spec from scratch
- The framework can generate an initial spec and then benefit from validation or contract-test feedback

## Mandatory Post-Extraction Workflow

Once the first spec has been extracted, the agent must execute these phases in order:

1. Save the extracted spec to the repo.
2. Inspect the generated spec for obvious gaps such as wrong status codes, generic `*/*` content types, missing security, weak request/response schemas, and missing error responses.
3. Refine generation using source annotations/config first. Use overlay only when source-level fixes cannot express the required contract.
4. Re-extract the spec after each meaningful refinement.
5. Before starting Specmatic contract tests, explicitly ask the user to confirm Docker Engine is running.
6. If Docker confirmation is provided, continue into the Specmatic feedback loop.
7. If Docker confirmation is not yet available, stop only after clearly reporting that extraction and refinement are done and the next blocked step is the Specmatic loop.

Do not treat annotation-only cleanup as the full post-extraction workflow.
Do not end the task after exporting `openapi.yaml` unless the user explicitly asks for extraction only.

## Content Guides

| Framework | Language | Guide |
|-----------|----------|-------|
| FastAPI | Python | [content/frameworks/fastapi.md](content/frameworks/fastapi.md) |
| Flask | Python | [content/frameworks/flask.md](content/frameworks/flask.md) |
| Django REST Framework | Python | [content/frameworks/django.md](content/frameworks/django.md) |
| Spring Boot | Java | [content/frameworks/spring-boot.md](content/frameworks/spring-boot.md) |
| ASP.NET Core | C# | [content/frameworks/aspnet.md](content/frameworks/aspnet.md) |
| Express | JavaScript | [content/frameworks/express.md](content/frameworks/express.md) |
| NestJS | TypeScript | [content/frameworks/nestjs.md](content/frameworks/nestjs.md) |
| Hono | TypeScript | [content/frameworks/hono.md](content/frameworks/hono.md) |
| Rails | Ruby | [content/frameworks/rails.md](content/frameworks/rails.md) |
| Laravel | PHP | [content/frameworks/laravel.md](content/frameworks/laravel.md) |

Each guide provides detailed setup, schema definition, authentication, and troubleshooting for that framework.

## When to Use

- User has an existing API application, service, or repository and wants to generate an OpenAPI or Swagger specification from it
- User asks to generate or extract an OpenAPI specification for "this application", "this project", "this service", or "this codebase"
- User says exactly or approximately: "Extract the OpenAPI specification from this application"
- User asks to create API schema, API docs, or Swagger docs from routes, controllers, annotations, or source code
- User mentions a specific framework (FastAPI, Flask, Django, Spring Boot, ASP.NET Core, Express, NestJS, Hono, Rails, Laravel)
- User says: "extract OpenAPI", "extract openapi spec", "generate openapi specification", "generate swagger", "create swagger from code", "code first", "generate spec from code", "existing API code"

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| Framework | Yes | The API framework in use (see Decision Framework) |
| Project path | Yes | Root directory of the API project |
| Output path | No | Where to write the spec (default: `openapi.json` or `openapi.yaml`) |

Note - Prefer YAML as default format and switch to JSON only if called out by user.

## Outputs

| Output | Description |
|--------|-------------|
| OpenAPI spec | A JSON or YAML file describing the API |

## Prerequisites

- The API project must be buildable and its dependencies installed
- For runtime extraction (FastAPI, Spring Boot, ASP.NET Core, NestJS, Hono), the app must be importable or startable

## Decision Framework

Use this tree to determine the extraction method:

| Framework | Language | Method | Requires Running Server? |
|-----------|----------|--------|--------------------------|
| FastAPI | Python | Built-in export | No |
| Flask (flask-smorest) | Python | CLI command | No |
| Django REST Framework | Python | drf-spectacular CLI | No |
| Spring Boot (springdoc) | Java | HTTP endpoint | Yes |
| ASP.NET Core | C# | HTTP endpoint | Yes |
| Express (swagger-jsdoc) | JavaScript | CLI or script | No |
| NestJS | TypeScript | HTTP endpoint or script | Yes |
| Hono (zod-openapi) | TypeScript | Programmatic export | No |
| Rails (rswag) | Ruby | Rake task | No |
| Laravel (l5-swagger) | PHP | Artisan command | No |

## Command

Choose the command matching your framework below.

### Python: FastAPI

FastAPI generates an OpenAPI schema at runtime. Export it without starting the server:

```bash
python -c "import json; from myapp import app; print(json.dumps(app.openapi()))" > openapi.json
```

Replace `myapp` with the module containing your FastAPI `app` instance. If the app uses a factory pattern:

```bash
python -c "import json; from myapp import create_app; app = create_app(); print(json.dumps(app.openapi()))" > openapi.json
```

You can also start the server and fetch from `http://localhost:8000/openapi.json`.

### Python: Flask (flask-smorest)

Requires [flask-smorest](https://flask-smorest.readthedocs.io/) or [apispec](https://apispec.readthedocs.io/):

```bash
flask openapi write openapi.json
```

If using apispec directly, export programmatically:

```python
import json
from myapp import create_app, spec
app = create_app()
with app.app_context():
    print(json.dumps(spec.to_dict()))
```

### Python: Django REST Framework

Requires [drf-spectacular](https://drf-spectacular.readthedocs.io/):

```bash
python manage.py spectacular --file openapi.yaml
```

For JSON output:

```bash
python manage.py spectacular --format openapi-json --file openapi.json
```

### Java: Spring Boot

Requires [springdoc-openapi](https://springdoc.org/). Start the application, then fetch the spec:

```bash
# Start the app (background)
./mvnw spring-boot:run &
# Wait for startup
sleep 15

# Fetch the spec
curl http://localhost:8080/v3/api-docs -o openapi.json

# For YAML format
curl http://localhost:8080/v3/api-docs.yaml -o openapi.yaml

# Stop the app
kill %1
```

If the server runs on a different port or context path, adjust the URL accordingly.

### C#: ASP.NET Core

Recommended for .NET 9+: [Microsoft.AspNetCore.OpenApi](https://learn.microsoft.com/aspnet/core/fundamentals/openapi/aspnetcore-openapi). Ensure your app maps the OpenAPI endpoint:

```csharp
builder.Services.AddOpenApi();
var app = builder.Build();
app.MapOpenApi(); // /openapi/v1.json
```

Then run the app and fetch the spec:

```bash
# Start the app (background)
dotnet run &
sleep 10

# Built-in OpenAPI endpoint (.NET 9+)
curl http://localhost:5000/openapi/v1.json -o openapi.json

# Stop the app
kill %1
```

If your app uses HTTPS or a different port, use the actual app URL from startup logs.

For legacy Swashbuckle-based projects, fetch from:

```bash
curl http://localhost:5000/swagger/v1/swagger.json -o openapi.json
```

For NSwag-based projects, fetch from:

```bash
curl http://localhost:5000/swagger/v1/swagger.json -o openapi.json
```

Important:
- Prefer `Microsoft.AspNetCore.OpenApi` for new .NET 9+ projects.
- For .NET 8 projects, prefer the Swashbuckle extraction path unless the project already uses NSwag.
- Do not run multiple OpenAPI stacks (built-in + Swashbuckle/NSwag) at once in the same app.
- See [content/frameworks/aspnet.md](content/frameworks/aspnet.md) for migration and transformer patterns.

### JavaScript: Express

Use [`swagger-jsdoc`](https://www.npmjs.com/package/swagger-jsdoc) to extract OpenAPI from `@openapi`/`@swagger` JSDoc blocks and optional YAML fragments.

CLI extraction (recommended):

```bash
# Install in project (or use npx)
npm install --save-dev swagger-jsdoc

# Generate OpenAPI JSON
npx swagger-jsdoc \
  -d swaggerDefinition.cjs \
  "src/**/*.js" \
  "src/**/*.yaml" \
  -o openapi.json
```

YAML output:

```bash
npx swagger-jsdoc \
  -d swaggerDefinition.cjs \
  "src/**/*.js" \
  "src/**/*.yaml" \
  -o openapi.yaml
```

`swaggerDefinition.cjs` example:

```javascript
module.exports = {
  openapi: "3.0.0",
  info: {
    title: "My Express API",
    version: "1.0.0",
  },
};
```

If route files are missing annotations, add `@openapi` blocks directly above handlers (or router definitions) before extraction. Minimum useful content per operation:
- `path` and HTTP method
- `summary` + stable `operationId`
- request input (`parameters` and/or `requestBody`)
- at least one concrete success response (for example `200` or `201`)
- relevant error responses (`400`, `401`, `404`, `500`) where applicable

Use shared `components/schemas` in YAML fragments for reusable DTOs, then reference them with `$ref` from route annotations.

See [content/frameworks/express.md](content/frameworks/express.md) for detailed setup, examples, and troubleshooting.

### TypeScript: NestJS

Requires [@nestjs/swagger](https://docs.nestjs.com/openapi/introduction). Start the application, then fetch:

```bash
# Start the app (background)
npm run start &
sleep 10

# Fetch the spec (default path with SwaggerModule)
curl http://localhost:3000/api-json -o openapi.json

# Stop the app
kill %1
```

Alternatively, create a script to export without running the server:

```typescript
// scripts/export-openapi.ts
import { NestFactory } from '@nestjs/core';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { AppModule } from '../src/app.module';
import * as fs from 'fs';

async function bootstrap() {
  const app = await NestFactory.create(AppModule, { logger: false });
  const config = new DocumentBuilder().setTitle('API').build();
  const doc = SwaggerModule.createDocument(app, config);
  fs.writeFileSync('openapi.json', JSON.stringify(doc, null, 2));
  await app.close();
}
bootstrap();
```

### TypeScript: Hono (zod-openapi)

Requires [@hono/zod-openapi](https://github.com/honojs/middleware/tree/main/packages/zod-openapi). Export the schema programmatically:

```typescript
// scripts/export-openapi.ts
import { app } from '../src/app';
import * as fs from 'fs';

const doc = app.doc('/doc', {
  openapi: '3.1.0',
  info: { title: 'API', version: '1.0.0' },
});
fs.writeFileSync('openapi.json', JSON.stringify(doc, null, 2));
```

Run with:

```bash
npx tsx scripts/export-openapi.ts
```

### Ruby: Rails (rswag)

Requires [rswag](https://github.com/rswag/rswag):

```bash
rails rswag:specs:swaggerize
```

The spec is written to `swagger/v1/swagger.yaml` by default (configurable in `config/initializers/rswag_api.rb`).

### PHP: Laravel (l5-swagger)

Requires [l5-swagger](https://github.com/DarkaOnLine/L5-Swagger):

```bash
php artisan l5-swagger:generate
```

The spec is written to `storage/api-docs/api-docs.json` by default.

## Post-Extraction Steps

After extracting the spec, run this feedback loop to validate and refine it.

### Specmatic Contract Test Feedback Loop

Use this skill when asked to run Specmatic contract tests against a system under test (SUT) and iteratively refine the OpenAPI specification until as many tests pass as possible.

Default behavior:
- As soon as spec extraction succeeds, immediately start this feedback loop and begin setup.
- Do not stop after extraction.
- If the feedback loop fails to start due to docker issues, ask user to start docker engine.
- Before entering the Docker-dependent loop, the agent should already have completed extraction, saved the spec, and completed the refinement phase above.
---

## Phase 1 — Setup

Follow this sequence strictly:

`pull image -> schema-valid config -> seed DB + generate examples -> validate examples -> run batch tests`

### 1. Pull the latest Specmatic image

Always pull the latest image before starting contract tests or stubs:

```bash
docker pull specmatic/enterprise:latest
```

### 2. Create `specmatic.yaml` using the official schema

Schema reference:
- https://github.com/specmatic/schemastore/blob/master/src/schemas/json/specmatic.json

Use `version: 3` config shape and place keys exactly where the schema expects them.

#### Validate config against official schema

Validate before first test run and after config edits:

```bash
npx --yes ajv-cli validate \
  -s https://raw.githubusercontent.com/specmatic/schemastore/master/src/schemas/json/specmatic.json \
  -d specmatic.yaml
```

#### Field placement map (V3)

| YAML path | Purpose |
|---|---|
| `systemUnderTest.service.definitions` | Contract source and list of specs under test |
| `systemUnderTest.service.runOptions.openapi` | Test runtime options (mode, baseUrl/host/port, filter, specs) |
| `systemUnderTest.service.runOptions.openapi.specs[].spec.overlayFilePath` | Overlay file to apply for spec corrections that are not feasible via source annotations |
| `systemUnderTest.service.data.examples` | External examples configuration for test/mock data |
| `systemUnderTest.service.data.dictionary` | Dictionary path when pattern substitutions are needed |
| `specmatic.settings.test.schemaResiliencyTests` | Controls schema resiliency test coverage |
| `specmatic.settings.test.maxTestRequestCombinations` | Runtime throttle when tests become too slow |

Baseline config (schema-aligned):

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

Default test settings rule:
- Always set `specmatic.settings.test.schemaResiliencyTests: all`.
- Do not add `specmatic.settings.test.maxTestRequestCombinations` to `specmatic.yaml` by default.
- Add `maxTestRequestCombinations` only after observing that too many contract tests are being generated or the suite is taking too long to run.
- Configure `specmatic.license.path` only if the license is actually present.
- If the license file is absent, omit `specmatic.license` entirely and let Specmatic use its built-in trial license.
- Do not fail the workflow only because the enterprise license file is missing.
- If the tests later fail due to license specific issues, ask user for the license path and set that in the config file.

Fail-fast rule:
- Treat any config key outside schema as invalid.
- Validate config before first test run; do not proceed until schema violations are fixed.

#### Configure overlay file path (required when overlay is used)

When you create `./specmatic/openapi.overlay.yaml`, enable it in `specmatic.yaml` at the spec runtime entry:

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
- Set `overlayFilePath` under `systemUnderTest.service.runOptions.openapi.specs[].spec` (not under `definitions`).
- Use a repo-relative path from project root (for example `./specmatic/openapi.overlay.yaml`).
- If multiple specs are tested, set `overlayFilePath` for each `spec` entry that needs overlay corrections.

### 3. Set up deterministic test data and external examples

External examples are used for deterministic positive-path scenarios and for stub behavior where concrete payloads are required.

Example directory conventions:
- Main API spec: `./specmatic/<spec-name>_examples/`
- Stub specs: `./specmatic/stub-<dependency-name>_examples/`

Per-batch rule:
- Regenerate/update external examples for each batch so payload values match seeded DB records for that run.
- Do not add examples for `400` scenarios. Let Specmatic generate and exercise invalid-request coverage through schema resiliency tests instead of pinning `400` cases as examples.

### 4. Add deterministic data-prep automation (required for loop execution)

Create a deterministic data-prep command (script or task) that runs before every batch and:
- Reset/create deterministic dummy data in SUT DB.
- Emit a run manifest with concrete values used in this run (`./build/specmatic/run-manifest.json`).
- Rewrite/templatise external examples using manifest values.

Example script template (`prepare_test_data.sh`):

```bash
#!/bin/bash
set -euo pipefail

BATCH_NAME="${1:-default}"
MANIFEST_DIR="./build/specmatic"
MANIFEST_PATH="$MANIFEST_DIR/run-manifest.json"
mkdir -p "$MANIFEST_DIR"

# 1) Seed deterministic DB data (replace with project-specific command)
# Examples:
# ./gradlew :web:seedContractData -Pbatch="$BATCH_NAME"
# psql "$DB_URL" -f scripts/seed_contract_data.sql

# 2) Emit deterministic manifest (IDs/timestamps generated for this batch)
cat > "$MANIFEST_PATH" <<JSON
{
  "batch": "$BATCH_NAME",
  "orderId": "ORD-$BATCH_NAME-001",
  "userId": "USR-$BATCH_NAME-001",
  "timestamp": "2026-01-01T00:00:00Z"
}
JSON

# 3) Rewrite external examples from manifest (replace with your tool/script)
# Example:
# node scripts/render_examples_from_manifest.js "$MANIFEST_PATH"

echo "Prepared deterministic data and examples for batch: $BATCH_NAME"
```

### 5. Validate examples before running tests

Validate external examples for schema fit and conflicting requests:

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

---

## Phase 2 — Batched Feedback Loop (Path-Prefix Strategy)

Do not test all APIs at once.

### Batch algorithm (default)

1. Discover API paths from the OpenAPI spec in `./specmatic/`.
2. Group paths by first segment (`/orders`, `/users`, `/invoices`, ...).
3. List these API groups to the user and ask which group(s) to harden first.
4. Create ordered batch filters (`BATCH_FILTERS`) only for user-selected groups.
5. For each selected batch:
   - Run deterministic data-prep command (for example `./prepare_test_data.sh <batch_name>`).
   - Revalidate examples.
   - Execute Specmatic tests only for that batch filter.
   - Fix fixable failures for that batch (annotations -> overlay -> stubs).
   - If batch hardening exceeds the time threshold (8-10 minutes, default 10), pause and ask:
     - continue current batch, or
     - defer this batch and move to next selected batch.
   - Summarize progress and ask user: **"Move to next batch of APIs?"**
6. After each completed/deferred batch, show remaining API groups and let user choose next.
7. Continue only on explicit user confirmation.
8. After all selected API groups have been tested, run one final Specmatic test pass for the full API surface without any `--filter`.
9. Use that final unfiltered run to generate the consolidated HTML report for all endpoints/APIs.

### User control prompts (required)

- Initial selection prompt:
  - "I found these API groups from the spec: <list>. Which group(s) do you want to harden first?"
- Long-running batch prompt (after 8-10 minutes, default 10):
  - "This batch is taking longer than expected. Do you want to continue this batch, or defer it and move to the next batch?"
- Next batch prompt:
  - "Do you want to move to the next batch of APIs from the remaining list?"

### Runtime throttle rule for long runs

If batch tests are too slow or too many test combinations are being generated:
1. Add `specmatic.settings.test.maxTestRequestCombinations` only after confirming the suite needs throttling.
2. Use `1` as a strong throttle when needed.
3. Note this is temporary and should be removed later for broader coverage.

### Batch progress reporting format

After each batch, report:
- `Batch`: current/total
- `Filter`: exact filter used
- `Duration`: elapsed time
- `Passed`
- `Failed (fixable)`
- `Failed (non-fixable)`
- `Remaining batches`
- `Deferred batches`

### Fix application order per batch

1. **Annotations/decorators** (preferred)
2. **OpenAPI overlay** (`./specmatic/openapi.overlay.yaml`)
3. **Specmatic stubs** for unreachable dependencies + stub examples

### Fix policy (strict)

- Always attempt annotations/decorators first for all spec mismatches.
- Add fixes to overlay only when they cannot be represented using annotations/decorators.
- If a mismatch cannot be fixed via annotations/decorators or overlay, classify it as **non-fixable** and report it for manual intervention.
- Do not create spec-preparation/spec-rewrite scripts to mutate the generated OpenAPI as a workaround for contract mismatches.

---

## Phase 3 — Final Deliverables

### Script: `run_contract_tests.sh` (single script, required)

At the end of the workflow, generate one runnable script for users to execute all contract tests in one go (no filter, no batches).

```bash
#!/bin/bash
set -euo pipefail

SUT_PORT=8090
PRE_TEST_SETUP_CMD="${PRE_TEST_SETUP_CMD:-}"

# -------------------------------------------------------
# PRE-REQUISITES:
# 1) SUT must be running on SUT_PORT
# 2) specmatic.yaml + specs + examples must already be prepared
# 3) optional deterministic setup command can be passed via PRE_TEST_SETUP_CMD
# -------------------------------------------------------

docker pull specmatic/enterprise:latest

# Optional runtime throttle for slow or overly large suites
# Add this only after you have observed that too many test combinations are being generated:
# yq -i '.specmatic.settings.test.maxTestRequestCombinations = 1' specmatic.yaml

# Optional deterministic setup hook (DB seed + example refresh)
if [ -n "$PRE_TEST_SETUP_CMD" ]; then
  echo "Running pre-test setup: $PRE_TEST_SETUP_CMD"
  eval "$PRE_TEST_SETUP_CMD"
fi

# Validate examples before full run
docker run --rm \
  -v "$(pwd)/specmatic:/usr/src/app/specmatic" \
  specmatic/enterprise examples validate \
  --spec-file "specmatic/<your-openapi-file.yaml>"

# Run full contract suite (all APIs, no --filter)
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

### README: `CONTRACT_TESTS_README.md`

Include:
- what `run_contract_tests.sh` does step-by-step
- required inputs/files: `specmatic.yaml`, specs, examples, running SUT, plus optional license file if present
- how to set `SUT_PORT`
- how to optionally pass deterministic setup hook via `PRE_TEST_SETUP_CMD`
- where to tune `specmatic.settings.test.maxTestRequestCombinations`
- how to switch from full run to filtered runs when needed
- known non-fixable failures table

---

## Phase 4 — Validation Checks (Doc-Driven Acceptance)

1. **Documentation consistency**
- `SKILL.md` must remain the single source of truth for this skill.
- All referenced config paths must match schema-defined V3 paths.

2. **Determinism checks**
- Same batch + same seed inputs -> same examples and same pass/fail set.
- Different seed manifest -> examples update consistently (no stale IDs).

3. **Batch loop checks**
- Only current batch APIs are tested per run via `--filter`.
- Loop pauses after each batch and asks user to continue.
- After the batch loop completes, one final full-suite run happens without `--filter`.
- Slow runs document and apply `maxTestRequestCombinations` throttle rule.

4. **Script contract checks**
- `run_contract_tests.sh` runs the full suite in one command without `--filter`.
- `run_contract_tests.sh` validates examples, runs tests, and outputs report path.

## Common Issues After Extraction

| Issue | Symptom | Fix |
|-------|---------|-----|
| Overly permissive schemas | Contract tests pass invalid payloads or miss shape regressions | Tighten request/response models in source code; avoid blanket `additionalProperties: true` unless intentional |
| Missing or weak response schemas | Response-body assertions are skipped or too generic | Add explicit response DTO/schema annotations and regenerate the spec |
| Duplicate or missing `operationId` values | Ambiguous failures in reports and poor traceability | Ensure each operation has a stable, unique `operationId` |
| Missing auth metadata | Protected endpoints fail with 401/403 during tests | Add `securitySchemes` and operation-level `security`; provide required auth headers in test setup |
| Stub specs without concrete examples | Stub starts but returns unusable data or Specmatic rejects responses | Add at least one concrete `examples` entry per stub response payload |
| Enum and nullability drift | Tests fail with "value not in enum" or nullability mismatch | Align source annotations/validators with real runtime behavior; use overlay only when annotations cannot express it |

## What NOT to Do

- **Do NOT** hand-write an OpenAPI spec when the framework can generate one -- always extract first
- **Do NOT** edit the extracted OpenAPI file directly for iterative fixes -- re-extraction will overwrite it; use annotations first, overlay second
- **Do NOT** modify business logic just to make contract tests pass -- adjust contract metadata and test setup instead
- **Do NOT** add custom scripts/tools that rewrite or preprocess the generated spec to bypass mismatches
- **Do NOT** mask mismatches with overly broad schemas (`type: object`, unrestricted maps, catch-all `any`) unless behavior is truly dynamic
- **Do NOT** assume extraction captured everything -- verify auth, error responses, headers, and downstream-dependent fields explicitly
- **Do NOT** keep stale overlay patches after source annotations are fixed -- remove redundant overlay rules to avoid configuration drift

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `Cannot connect to the Docker daemon` | Docker Engine is not running | Start Docker Desktop/Engine, then rerun tests |
| Specmatic cannot reach the SUT (`Connection refused`, timeout) | Wrong SUT port, SUT not started, or bind/address mismatch | Start SUT first, verify it is reachable locally, and match `SUT_PORT`/`baseUrl` values |
| `host.docker.internal` resolution/connectivity issues (Linux/CI) | Docker host alias not configured in that environment | Keep `--add-host host.docker.internal:host-gateway`; in CI/Linux, provide an equivalent host mapping if needed |
| Overlay changes are ignored | `overlayFilePath` not enabled or wrong path in `specmatic.yaml` | Uncomment and correct `overlayFilePath`, then rerun |
| Stub returns invalid or empty responses | Stub spec lacks concrete response examples or wrong port mapping | Add concrete `examples` in stub spec and verify `-p <host>:<container>` port mapping |
| `License file not found` / enterprise feature error | `specmatic.license.path` was configured but `specmatic-unlimited-license.txt` is missing or wrong | If the file exists, correct the path; otherwise remove `specmatic.license` and use Specmatic's built-in trial license |
| Empty or minimal extracted spec | Routes not registered at import/startup time | Ensure all route modules are imported and app startup path loads the full router tree |
| Framework doc endpoint missing (`/v3/api-docs`, `/api-json`) | OpenAPI library not configured or route path differs | Configure springdoc/@nestjs/swagger and verify the actual docs endpoint path |

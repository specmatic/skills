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

Extract and refine an OpenAPI specification from an existing API codebase.

## Required Behavior

If this skill is selected, do all of the following:

- In the first user-facing progress update, explicitly say you are using `specmatic-openapi-spec-extractor`.
- Treat extraction as phase 1, not the final outcome.
- After extraction succeeds, continue into the mandatory post-extraction workflow below. Do not stop after saving the first generated spec.
- Prefer source annotations/config first, overlay second, and direct edits to the extracted spec never.
- If a later phase is blocked, explicitly say which phase is blocked and why.
- Do not silently behave like a generic OpenAPI extraction task. Follow this skill's workflow explicitly.

Default execution order:

`announce skill -> identify framework -> open one framework guide -> extract spec -> save spec -> inspect gaps -> refine -> re-extract -> ask for Docker confirmation -> run Specmatic feedback loop`

Use this exact style in the first progress update:

- `Using specmatic-openapi-spec-extractor to extract and refine the OpenAPI spec. I’m first identifying the framework and extraction path, then I’ll continue with post-extraction refinement.`

## Selection Heuristics

Select this skill by default when the user asks to extract or generate an OpenAPI or Swagger spec from an existing application, even if they do not mention Specmatic, skills, validation, refinement, or overlays.

This skill should win over a generic extraction-only skill when:

- The request is about "this application", "this project", or "this codebase"
- The user wants the spec to be accurate, complete, hardened, or refined
- The task involves an existing API implementation rather than writing a spec from scratch
- The framework can generate an initial spec and then benefit from contract-test feedback

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

## When to Use

- User has an existing API application, service, or repository and wants to generate an OpenAPI or Swagger specification from it
- User asks to generate or extract an OpenAPI specification for "this application", "this project", "this service", or "this codebase"
- User says exactly or approximately: "Extract the OpenAPI specification from this application"
- User asks to create API schema, API docs, or Swagger docs from routes, controllers, annotations, or source code
- User mentions a specific framework covered below

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| Framework | Yes | The API framework in use |
| Project path | Yes | Root directory of the API project |
| Output path | No | Where to write the spec (default: `openapi.yaml`) |

## Outputs

| Output | Description |
|--------|-------------|
| OpenAPI spec | Extracted JSON or YAML contract |
| Refined source metadata | Annotation/config updates used to improve regenerated output |

## Prerequisites

- The API project must be buildable and its dependencies installed
- For runtime extraction, the app must be importable or startable

## Decision Framework

| Framework | Method | Open this guide |
|-----------|--------|-----------------|
| FastAPI | Built-in export | [content/frameworks/fastapi.md](content/frameworks/fastapi.md) |
| Flask | CLI/programmatic export | [content/frameworks/flask.md](content/frameworks/flask.md) |
| Django REST Framework | `drf-spectacular` CLI | [content/frameworks/django.md](content/frameworks/django.md) |
| Spring Boot | Runtime docs endpoint | [content/frameworks/spring-boot.md](content/frameworks/spring-boot.md) |
| ASP.NET Core | Runtime docs endpoint | [content/frameworks/aspnet.md](content/frameworks/aspnet.md) |
| Express | `swagger-jsdoc` | [content/frameworks/express.md](content/frameworks/express.md) |
| NestJS | Runtime docs endpoint or script | [content/frameworks/nestjs.md](content/frameworks/nestjs.md) |
| Hono | Programmatic export | [content/frameworks/hono.md](content/frameworks/hono.md) |
| Rails | `rswag` task | [content/frameworks/rails.md](content/frameworks/rails.md) |
| Laravel | `l5-swagger` command | [content/frameworks/laravel.md](content/frameworks/laravel.md) |

## Reference Routing

Use the smallest amount of reference material needed.

- For extraction:
  Open only the matching framework guide from `content/frameworks/`.
- After the first extraction succeeds:
  Open [content/specmatic-loop.md](content/specmatic-loop.md).
- When generating `specmatic.yaml`, examples, overlays, or deterministic setup:
  Open [content/specmatic-setup.md](content/specmatic-setup.md).
- When preparing final scripts, docs, or acceptance checks:
  Open [content/specmatic-deliverables.md](content/specmatic-deliverables.md).

Do not bulk-read all reference files. Identify the framework first, then open only the file needed for the current phase.

## Specmatic References

- [content/specmatic-loop.md](content/specmatic-loop.md): post-extraction loop, Docker gate, batching, and fix order
- [content/specmatic-setup.md](content/specmatic-setup.md): `specmatic.yaml`, overlays, examples, licensing, and deterministic setup
- [content/specmatic-deliverables.md](content/specmatic-deliverables.md): final scripts, README expectations, acceptance checks, and troubleshooting

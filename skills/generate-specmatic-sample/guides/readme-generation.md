# README Generation Guide

Generated READMEs serve two purposes: help developers run the sample AND demonstrate why Specmatic matters. The README is a selling point for Specmatic, not just setup instructions.

## Required Sections (in order)

### 1. Title + Table of Contents

```
# Specmatic Sample: <Framework> <App-Type> (<Protocol>)

Table of Contents
* [Background](#background)
* [Tech](#tech)
* [Run Contract Tests](#run-contract-tests)
* [How It Works](#how-it-works)
* [Project Structure](#project-structure)
* [For More Info](#for-more-info)
```

Example: `# Specmatic Sample: Spring Boot Order API (REST/OpenAPI)`

### 2. Background

One paragraph explaining what this sample demonstrates. Include:
- The application type (backend, BFF, frontend)
- The protocol being contract-tested
- That Specmatic auto-generates tests from the API spec
- Which specs are used (with links to the actual contract files in the contract repo)
- What dependencies are stubbed/mocked by Specmatic

Example tone: "In this sample project, we will use Specmatic to contract test
the Order API in isolation. The interaction between the Order API and its
consumers is governed by this OpenAPI specification."

List the specs used with links:
```markdown
* [Order API's OpenAPI spec](https://github.com/specmatic/specmatic-order-contracts/blob/main/io/specmatic/examples/store/openapi/api_order_v3.yaml) is used for running contract tests against the API.
* [Domain API's OpenAPI spec](https://github.com/specmatic/specmatic-order-contracts/blob/main/io/specmatic/examples/store/openapi/api_order_v3.yaml) is used for stubbing the Domain API.
```

### 3. Why Specmatic

Bullet list of benefits. Keep it to 3-4 points, protocol-aware. Focus on what
Specmatic uniquely offers, not generic contract testing concepts:

- **Auto-generated tests from your API spec** — Specmatic reads your OpenAPI/AsyncAPI/gRPC/GraphQL/WSDL spec and generates test cases automatically. No hand-written test code or mocks to maintain.
- **Intelligent service virtualisation** — Specmatic generates realistic stubs/mocks from the same spec, so consumers can develop in parallel without waiting for providers.
- **Backward compatibility detection** — Specmatic compares spec versions and flags breaking changes before they reach production.
- **Single source of truth** — one spec drives contract tests, stubs, and backward compatibility checks. No drift between tests and documentation.

For protocol-specific benefits, add one relevant point:
- REST/OpenAPI: "Works with your existing OpenAPI spec — no new DSL to learn."
- AsyncAPI/Kafka: "Validates message producers and consumers against your AsyncAPI contract without a running broker."
- gRPC: "Tests your Protobuf service definitions without spinning up dependent services."
- GraphQL: "Validates queries, mutations, and schema compliance from your GraphQL SDL."
- SOAP/WSDL: "Contract tests your SOAP services using existing WSDL definitions."

### 4. Architecture Image

Include an animated GIF showing the interaction flow. Copy the appropriate
diagram from this skill's `assets/` folder into the sample's `assets/` folder:

- **Backend**: `assets/specmatic-order-backend-architecture.gif` (bundled in skill — for understanding purpose, may not be fully accurate with the generated sample's architecture)
- **BFF**: `assets/specmatic-order-bff-architecture.gif` (bundled in skill)
- **Frontend**: `assets/specmatic-order-frontend-architecture.gif` (bundled in skill)

For app types where a diagram is not yet bundled in the skill,
skip this section rather than generating a placeholder. Record
"architecture diagram not available" in the manifest learnings.

Markdown reference in README:
```markdown
![HTML client talks to BFF API which in-turn talks to backend API](assets/specmatic-order-bff-architecture.gif)
```

### 5. Tech

Numbered list of key technologies:
1. Language + Framework (e.g., "Spring Boot service written in Java")
2. Specmatic Enterprise with the exact runtime artifact or Docker image used
3. Docker Desktop (when the integration mode requires it)
4. Any notable runtime requirement (e.g., "JRE 17+", "Node 20+")

### 6. Run Contract Tests

Structure:
- **Prerequisites** — list what must be installed (JRE 17+, language runtime, etc.).
  Include `SPECMATIC_LICENSE_KEY` and the exact Enterprise runtime artifact
  used by the sample, such as `io.specmatic.enterprise:executable-all:<version>`
  or `specmatic/enterprise:<tag>`. Do not describe the public/open-source
  `specmatic` npm package as the runtime.
- **Using the build tool** — the primary single-command path with all three OS variants:

```markdown
For **Unix based systems** and **Windows PowerShell**:
```shell
./mvnw test
```

For **Windows Command Prompt**:
```shell
mvnw.cmd test
```
```

- **Using Docker** — if applicable, show the `docker run` commands with volume mounts
- **View Specmatic Test Reports** — link to the HTML and CTRF reports generated
  by Specmatic after the test command runs. Do not describe or add any
  sample-owned report renderer. Use the actual verified report directory from
  the sample manifest; do not assume or hard-code a report path.

```markdown
#### View Specmatic Test Reports

After running the contract tests, you can view the HTML report generated by
Specmatic in [<verified-report-directory>](<verified-report-directory>/). The
same directory also contains the CTRF output for CI tooling.
```

Always show commands for all three OS variants: Unix/macOS, Windows PowerShell,
and Windows Command Prompt.

Include a note about first-run timing: "First run may take 1-2 minutes as Specmatic clones the configured contract repository. Subsequent runs are fast (cached in `.specmatic/`)."

Link to the specmatic.yaml file and explain it configures which contracts are tested.

Include a "Test Modes" subsection explaining how to enable schema resiliency:

```markdown
### Test Modes

This sample ships with `schemaResiliencyTests: all` which runs the full test
suite including negative/boundary tests. You can adjust the mode in
`specmatic.yaml`:

| Mode | What it does |
|------|-------------|
| `none` | Runs tests from named examples only (fastest) |
| `positiveOnly` | Adds all valid input combinations |
| `all` | Adds negative/boundary tests — expects 400 for invalid inputs (default) |

To change, update `specmatic.yaml`:
```yaml
specmatic:
  settings:
    test:
      schemaResiliencyTests: none
```
```

### 7. How It Works

Brief explanation of the contract testing flow specific to this sample's role:

**Backend:**
```
API Spec (OpenAPI/Proto/etc.) → specmatic.yaml → Specmatic generates requests → Your service responds → Specmatic validates responses against the spec
```

**BFF:**
```
BFF Spec → specmatic.yaml → Specmatic generates requests to your BFF → Your BFF calls dependency (Specmatic mock) → Specmatic validates both sides
```

**Frontend:**
```
BFF Spec → specmatic.yaml → Specmatic mocks the BFF API → Your frontend calls the mock → Contract compliance verified
```

Explain in 2-3 sentences what happens when you run the test command. Mention that Specmatic reads `specmatic.yaml`, fetches the contract, and auto-generates test cases.

### 8. Project Structure

Table of key files:

```markdown
| File | Purpose |
|------|---------|
| `specmatic.yaml` | Contract test configuration — points to the API spec |
| `src/...` or equivalent | Application source code |
| `test/...` or equivalent | Contract test adapter that starts the app and runs Specmatic |
| `Dockerfile` | Production container image |
| `.github/workflows/ci.yml` | CI pipeline: test + Docker build |
```

Adjust paths for the actual generated structure.

### 9. For More Info

- [Specmatic Website](https://specmatic.io)
- [Specmatic Documentation](https://docs.specmatic.io)
- Link to the specific contract/spec used by this sample

## Optional Sections

Include these when relevant to the sample:

### Configuration

Table of environment variables that can override defaults:

```markdown
| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| SUT_PORT | 8080 | Application port |
| SUT_BASE_URL | http://localhost:8080 | Base URL for Specmatic tests |
```

Include when the sample exposes configurable ports, URLs, or broker settings.

Place optional sections between "How It Works" and "Project Structure".

## Tone and Style

- Written for a developer who just found this repo — they should understand WHY in 30 seconds
- Concise, not marketing-heavy — benefits backed by what the sample actually demonstrates
- Use code blocks for commands
- Keep the total README under 120 lines when possible

## Maintain-Mode Update Rules

When updating an existing README during maintain mode:

1. **Preserve user-added sections** — any section not in the required list above should be kept in place
2. **Add missing required sections** — if "Background" or "How It Works" doesn't exist, add it in the correct position
3. **Refresh factual content** — update version numbers, commands, prerequisite versions, and contract links to match current state
4. **Don't rewrite working prose** — if a section exists and is accurate, leave it alone
5. **Update Project Structure table** — reflect any file changes from the maintain session

# ASP.NET Core OpenAPI Extraction

This guide covers extracting an OpenAPI spec from existing ASP.NET Core APIs, with support for modern built-in OpenAPI, legacy Swashbuckle setups, and NSwag.

Framework-native rule:
- Use the framework-native OpenAPI stack required by the target app: built-in OpenAPI for .NET 9+, Swashbuckle for .NET 8, or existing NSwag projects where already present.
- If the required OpenAPI package/endpoint/config is missing, add the minimum non-behavioral integration required, then extract from the generated endpoint.
- Do not substitute a manually authored primary spec for ASP.NET Core.

## Choose by Target Framework

| Target framework | Primary extraction path | Typical endpoint |
|---|---|---|
| .NET 8 | Swashbuckle (primary) | `/swagger/v1/swagger.json` |
| .NET 9+ | Microsoft.AspNetCore.OpenApi (recommended) | `/openapi/v1.json` |
| Any (existing NSwag project) | NSwag (keep as-is) | `/swagger/v1/swagger.json` |

## Recommended Approach (.NET 9+)

Use `Microsoft.AspNetCore.OpenApi` (first-party package).

### Basic Setup

```csharp
// Program.cs
// If missing: <PackageReference Include="Microsoft.AspNetCore.OpenApi" Version="9.*" />
// Keep package major version aligned to your target framework major version.

builder.Services.AddOpenApi();

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.MapOpenApi(); // serves /openapi/v1.json
}
```

Notes:
- `MapOpenApi()` serves raw OpenAPI JSON. UI tooling is separate.
- For .NET 10, OpenAPI 3.1 is supported by default.

## Extraction Commands

### Built-in OpenAPI endpoint (.NET 9+)

```bash
# from project root

dotnet run &
APP_PID=$!

for i in {1..30}; do
  if curl -fsS http://localhost:5000/openapi/v1.json -o openapi.json; then
    break
  fi
  sleep 1
done

kill "$APP_PID"
```

If your app binds to another URL/port (for example `https://localhost:5001`), use that URL from startup logs.

### Legacy Swashbuckle endpoint

For .NET 8 projects, ensure Swashbuckle is configured before extracting:

```csharp
// Program.cs
// <PackageReference Include="Swashbuckle.AspNetCore" Version="6.*" />

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var app = builder.Build();
app.UseSwagger();
app.UseSwaggerUI();
```

Then extract with retry/polling (instead of fixed sleep):

```bash
dotnet run &
APP_PID=$!

for i in {1..30}; do
  if curl -fsS http://localhost:5000/swagger/v1/swagger.json -o openapi.json; then
    break
  fi
  sleep 1
done

kill "$APP_PID"
```

### NSwag endpoint

If the project already uses NSwag, keep existing setup:

```csharp
// Program.cs
// <PackageReference Include="NSwag.AspNetCore" Version="14.*" />
builder.Services.AddOpenApiDocument();
var app = builder.Build();
app.UseOpenApi();
app.UseSwaggerUi();
```

```bash
dotnet run &
APP_PID=$!

for i in {1..30}; do
  if curl -fsS http://localhost:5000/swagger/v1/swagger.json -o openapi.json; then
    break
  fi
  sleep 1
done

kill "$APP_PID"
```

## Multiple Documents

If the app registers multiple docs:

```csharp
builder.Services.AddOpenApi("v1", options =>
{
    options.OpenApiVersion = OpenApiSpecVersion.OpenApi3_0;
});

builder.Services.AddOpenApi("v2", options =>
{
    options.OpenApiVersion = OpenApiSpecVersion.OpenApi3_1;
});

var app = builder.Build();
app.MapOpenApi();
```

Extract each document explicitly:

```bash
curl http://localhost:5000/openapi/v1.json -o openapi.v1.json
curl http://localhost:5000/openapi/v2.json -o openapi.v2.json
```

## Migration Guidance (Swashbuckle -> Built-in)

For .NET 9+ projects, prefer `Microsoft.AspNetCore.OpenApi`.

- Swashbuckle is not actively maintained and does not support OpenAPI 3.1.
- Avoid mixing built-in OpenAPI and Swashbuckle in the same app.

Migration checklist:
1. Remove Swashbuckle package references.
2. Replace `builder.Services.AddSwaggerGen(...)` with `builder.Services.AddOpenApi(...)`.
3. Replace `app.UseSwagger()` with `app.MapOpenApi()`.
4. If a UI is needed, add Scalar or Swagger UI separately.

## Document and Operation Transformers

Use transformers to enrich the extracted spec without changing business logic.

### Document transformer example

```csharp
builder.Services.AddOpenApi(options =>
{
    options.AddDocumentTransformer((document, context, ct) =>
    {
        document.Info = new Microsoft.OpenApi.Models.OpenApiInfo
        {
            Title = "Orders API",
            Version = "v1"
        };
        return Task.CompletedTask;
    });
});
```

### Operation transformer example

```csharp
builder.Services.AddOpenApi(options =>
{
    options.AddOperationTransformer((operation, context, ct) =>
    {
        operation.Extensions["x-api-group"] = new Microsoft.OpenApi.Any.OpenApiString("orders");
        operation.Extensions["x-operation-name"] = new Microsoft.OpenApi.Any.OpenApiString("create");
        return Task.CompletedTask;
    });
});
```

## Authentication Metadata

Use document transformers to add security schemes to the generated spec:

```csharp
builder.Services.AddOpenApi(options =>
{
    options.AddDocumentTransformer((document, context, ct) =>
    {
        document.Components ??= new Microsoft.OpenApi.Models.OpenApiComponents();
        document.Components.SecuritySchemes["BearerAuth"] = new Microsoft.OpenApi.Models.OpenApiSecurityScheme
        {
            Type = Microsoft.OpenApi.Models.SecuritySchemeType.Http,
            Scheme = "bearer",
            BearerFormat = "JWT"
        };
        return Task.CompletedTask;
    });
});
```

## OpenAPI 3.1 (.NET 10)

.NET 10 adds full OpenAPI 3.1 generation support (JSON Schema draft 2020-12 alignment).

```csharp
builder.Services.AddOpenApi(options =>
{
    options.OpenApiVersion = OpenApiSpecVersion.OpenApi3_1;
});
```

Use this when downstream tooling requires 3.1 features.

## Agent Gotchas

- Do not use mismatched major versions for `Microsoft.AspNetCore.OpenApi` and the target framework.
- Do not describe Swashbuckle as formally deprecated; call it not actively maintained.
- Do not forget that `MapOpenApi()` only serves JSON; it does not provide UI by itself.
- Do not run built-in OpenAPI and Swashbuckle/NSwag generators together in one app.

## Common Issues

| Issue | Solution |
|-------|----------|
| `/openapi/v1.json` returns 404 | Ensure `builder.Services.AddOpenApi()` and `app.MapOpenApi()` are configured |
| `/swagger/v1/swagger.json` returns 404 in .NET 8 | Ensure `AddSwaggerGen()` and `UseSwagger()` are configured, and expected document name is `v1` |
| Connection refused during extraction | Wait for app startup or use the actual bound URL from logs |
| Empty/incomplete document | Verify endpoint metadata and route registration are loaded at startup |
| Package/API mismatch errors | Align `Microsoft.AspNetCore.OpenApi` major version with target framework |
| Need UI but only JSON is available | Add Scalar or Swagger UI as a separate component |

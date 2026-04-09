# Express OpenAPI Extraction (swagger-jsdoc)

This guide covers extracting an OpenAPI spec from existing Express APIs using `swagger-jsdoc`.

Use `swagger-jsdoc` as a CLI tool from npm.

## Prerequisites

- Node.js 20+ (per `swagger-jsdoc` package requirements)
- Express route handlers annotated with `@openapi` or `@swagger` blocks, and/or YAML fragments

## Install

```bash
npm install --save-dev swagger-jsdoc
```

## Minimal Definition File

Create `swaggerDefinition.cjs` at project root:

```javascript
module.exports = {
  openapi: '3.0.0',
  info: {
    title: 'My Express API',
    version: '1.0.0',
  },
};
```

## Example Route Annotation

```javascript
/**
 * @openapi
 * /health:
 *   get:
 *     summary: Health check
 *     responses:
 *       200:
 *         description: OK
 */
app.get('/health', (req, res) => {
  res.json({ ok: true });
});
```

## When Annotations Are Missing

If routes do not have `@openapi` / `@swagger` blocks yet, add them incrementally and regenerate the spec after each batch.

Recommended order:
1. Annotate read endpoints first (`GET` list/detail).
2. Annotate write endpoints (`POST`, `PUT`, `PATCH`, `DELETE`) with request bodies.
3. Move reusable schemas into shared YAML component files and reference via `$ref`.

Minimum operation template:

```javascript
/**
 * @openapi
 * /orders/{id}:
 *   get:
 *     summary: Get order by id
 *     operationId: getOrderById
 *     tags:
 *       - Orders
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema:
 *           type: string
 *     responses:
 *       200:
 *         description: Order found
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/Order'
 *       404:
 *         description: Order not found
 */
router.get('/orders/:id', getOrderById);
```

Write endpoint template:

```javascript
/**
 * @openapi
 * /orders:
 *   post:
 *     summary: Create order
 *     operationId: createOrder
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             $ref: '#/components/schemas/CreateOrderRequest'
 *     responses:
 *       201:
 *         description: Created
 */
router.post('/orders', createOrder);
```

Example shared components file (`src/openapi/components.yaml`):

```yaml
components:
  schemas:
    Order:
      type: object
      required: [id, status]
      properties:
        id:
          type: string
        status:
          type: string
          enum: [NEW, PROCESSING, COMPLETE]
```

## Extraction Commands

### JSON output (recommended default)

```bash
npx swagger-jsdoc \
  -d swaggerDefinition.cjs \
  "src/**/*.js" \
  "src/**/*.yaml" \
  -o openapi.json
```

### YAML output

```bash
npx swagger-jsdoc \
  -d swaggerDefinition.cjs \
  "src/**/*.js" \
  "src/**/*.yaml" \
  -o openapi.yaml
```

Notes:
- Paths are resolved relative to the current working directory.
- Glob patterns are supported (for example `**/*.js`).
- Output defaults to `swagger.json` if `-o` is omitted.

## Node API Fallback

When CLI usage is not suitable, generate with the Node API:

```javascript
const fs = require('fs');
const swaggerJsdoc = require('swagger-jsdoc');

const spec = swaggerJsdoc({
  failOnErrors: true,
  definition: {
    openapi: '3.0.0',
    info: { title: 'My Express API', version: '1.0.0' },
  },
  apis: ['src/**/*.js', 'src/**/*.yaml'],
});

fs.writeFileSync('openapi.json', JSON.stringify(spec, null, 2));
```

## Common Issues

| Issue | Solution |
|-------|----------|
| Empty `paths` in output | Ensure `@openapi`/`@swagger` blocks exist and glob patterns include the right files |
| CLI says definition file not found | Verify `-d` path and run command from the project root |
| Invalid generated spec | Use `failOnErrors: true` in Node API flow to fail fast and fix malformed annotations |
| Missing YAML fragments | Include YAML files explicitly in CLI arguments/glob patterns |
| Shell does not expand globs as expected | Quote globs (`"src/**/*.js"`) and run from the intended working directory |
| Paths exist but schemas are weak or missing | Add explicit `parameters`, `requestBody`, and `responses.content.schema` (prefer `$ref` to shared components) |

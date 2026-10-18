# store-resource-bootstrap

Optional **resource bootstrap plugin** for the common-store data-layer family. It wires the host's resource capability (`providers` / `url` / `sign` / `schema` / `fields`) and produces the store-api file-seam resolvers (`download` / `upload` / `uploadResolver`) used for file **download** and **upload**.

> 中文说明：[README.zh-CN.md](./README.zh-CN.md)
> Single source of truth: [`spec/00-protocol.md`](./spec/00-protocol.md)

## 2. Runtime / package matrix

| Runtime | Package name | Version | Import | Host package (optional peer) | Engine floor |
|---|---|---|---|---|---|
| Node | `store-resource-bootstrap-node` | `0.3.1` | `require('store-resource-bootstrap-node')` | `nodejs-store >= 4.3.0` | `node >= 18` |
| Python | `store-resource-bootstrap-py` | `0.3.1` | `from store_resource_bootstrap import capability, adapter` | `py-store >= 4.3.0` | `python >= 3.10` |

Each runtime's public surface has three namespaces:

| Namespace | Members | Purpose |
|---|---|---|
| `capability` | `schemas()`, `create(store, opts)` | register caller-injected schemas + configure the host resource pool |
| `adapter` | `download(store, opts)`, `upload(store)`, `uploadResolver(store, opts)` | produce the store-api file-seam resolvers |
| `providers` | `oss`, `minio` | optional reference S3-compatible provider factories |

Optional third-party SDKs (declared as optional, **lazily loaded** — the package imports and the `capability` / `adapter` namespaces work without them; only actually calling a provider's `create()` needs the SDK):

| Runtime | SDK | Declared as |
|---|---|---|
| Node | `@aws-sdk/client-s3 ^3.1146.0` | `optionalDependencies` |
| Python | `boto3 >= 1.34` | optional extra `providers` (`pip install "store-resource-bootstrap-py[providers]"`) |

The host packages (`nodejs-store` / `py-store`) are declared as **optional peer dependencies only** — they are never imported or required by this plugin; the store instance is always passed in by the integrator.

## 3. Table of contents

1. [Title + positioning](#store-resource-bootstrap)
2. [Runtime / package matrix](#2-runtime--package-matrix)
3. [Table of contents](#3-table-of-contents)
4. [What it is](#4-what-it-is)
5. [When to use / when not to use](#5-when-to-use--when-not-to-use)
6. [Installation](#6-installation)
7. [Quick start](#7-quick-start)
8. [Capability bootstrap (`capability.*`)](#8-capability-bootstrap)
9. [Adapter reference (`download` / `upload` / `uploadResolver`)](#9-adapter-reference)
10. [Providers (`oss` / `minio` / `s3-compat`)](#10-providers)
11. [Configuration reference (the seven keys)](#11-configuration-reference)
12. [`fields` mapping (logical role → physical field)](#12-fields-mapping)
13. [DDL boundary](#13-ddl-boundary)
14. [Error mapping](#14-error-mapping)
15. [Scenarios](#15-scenarios)
16. [Customisation / extension points](#16-customisation--extension-points)
17. [Boundaries and non-goals](#17-boundaries-and-non-goals)
18. [FAQ](#18-faq)
19. [Development](#19-development)
20. [Related projects](#20-related-projects)
21. [License](#21-license)

## 4. What it is

`store-resource-bootstrap` sits in the common-store **plugin / glue layer** (it is *not* a protocol skin, *not* a host, *not* core). Its shape mirrors `store-rbac-bootstrap`: read configuration → hook into existing seams. It does exactly two things:

1. **Capability bootstrap** — register the caller-**injected** schema definitions (`schemas`, optional; nothing is registered by default) into the host store, then call the host's existing resource façade `configureResource({ providers, url, sign, schema, fields })`.
2. **Seam adaptation** — produce the `fileResolver` (`download`) and `uploadResolver` (upload) that a skin needs, plus a thin pass-through `resourcePut` (`upload`).

It exposes two explicit namespaces — `capability` (bootstrap: `schemas` / `create`) and `adapter` (seam: `download` / `upload` / `uploadResolver`) — and ships one **optional reference provider namespace** `providers` (`oss` / `minio`, S3-compatible presets) that integrators may reference directly in `providerPlugins`.

**Where it sits in the architecture.** The host (`nodejs-store` / `py-store`) owns the resource capability itself: the schema registry, the resource pool built from `providers`, and — from `4.3.0` on — the `configureResource({ fields })` field mapping and the `resourceOpen` read that also returns `fileName` / `mime`. The skin (`store-api`) owns HTTP exposure: the `GET` / `POST /{resource}/:id/file` sub-route fetches bytes through an injected `fileResolver` and stores bytes through an injected `uploadResolver`. This plugin owns neither: it is the piece that **configures the capability** and **produces the resolvers**, so the business only writes glue and never re-implements HTTP routing or DDL.

**Schema ownership.** The library ships **no authoritative resource schema**.

- **Business-entity schemas** (e.g. the tables behind `product.images` / `user.avatar`) are never touched — the business layer defines and owns them; this library is zero-definition, zero-placeholder for them.
- The **resource capability's own metadata schemas** (`Resource` / `ResourceLocation` / `ResourceBinding`) are shipped **only as an optional reference** via `capability.schemas()`. Whether to register them is decided by the integrator through `opts.schemas` (default `[]` → **nothing is registered**, so DDL and the resource model are entirely up to the business/host).
- The **column structure of the three resource tables is likewise business-definable**: their column names are not hard-coded in the host; the integrator declares them through the `opts.fields` "logical role → physical field name" mapping (default = canonical column names).

Three invariants:

- **Zero semantic invention** — the plugin produces no HTTP status code, no error name, no error prefix; it throws plain `Error` (Node) / `ValueError` (Python). The download `404` semantics live in the existing store-api skin.
- **Zero host dependency** — it never `require('nodejs-store')` / `from py_store import ...`, and never depends on any core or skin package; the store instance is passed in as an argument.
- **Zero regression** — it modifies no sibling repository; it is purely additive.

## 5. When to use / when not to use

**Use it when** you are integrating the common-store resource capability into a service and you want:

- a one-call way to register resource schemas and configure the resource pool on the host store;
- ready-made `fileResolver` / `uploadResolver` objects to hand to `store-api`, so bytes flow through the existing `/{resource}/:id/file` sub-route with no new HTTP route;
- the resource-table column names to be configurable (`fields`) without touching business code;
- an S3-compatible `oss` / `minio` provider factory without writing your own storage adapter.

**Do not use it when** you expect it to:

- create tables or run DDL (it never does — see §13);
- expose HTTP routes or produce status codes / error names (that is `store-api`'s job);
- own or define your business-entity schemas (the business owns them);
- generate presigned URLs or upload directly to storage bypassing the data layer (**not provided** — uploads go through the host's `resourcePut`; see §16/§17).

## 6. Installation

### Node

```bash
npm i store-resource-bootstrap-node
# only if you use the optional oss / minio providers:
npm i @aws-sdk/client-s3
```

### Python

```bash
pip install store-resource-bootstrap-py
# only if you use the optional oss / minio providers:
pip install "store-resource-bootstrap-py[providers]"
```

The plugin has **no third-party runtime dependency by default** (Node / Python standard library is enough). The optional `oss` / `minio` modules need an S3-compatible SDK (`@aws-sdk/client-s3` / `boto3`), which is **lazily loaded**: when not installed, the module still loads and `capability` / `adapter` and the tests are unaffected — only actually calling that module's `create()` throws.

## 7. Quick start

### Node (`store-resource-bootstrap-node`)

```js
const { store } = require('nodejs-store');                 // host store (passed in by the integrator)
const { capability, adapter } = require('store-resource-bootstrap-node');

// Capability bootstrap: inject schema definitions as needed and configure the resource pool.
// `schemas` defaults to [] → registers nothing; pass capability.schemas() for the built-in
// optional reference set, or your own definitions.
const handle = capability.create(store, {
  providers: [{ kind: 'local', options: { root: '/data/resources' }, priority: 0 }],
  schemas: capability.schemas(),
});
const out = await handle.start();
// out === { registered: ['Resource', 'ResourceLocation', 'ResourceBinding'], skipped: [], providerRegistered: [] }
// await handle.reload();  // re-runs start()

// Seam adaptation: a store-api fileResolver for GET  /{resource}/:id/file
const fileResolver = adapter.download(store);
// Seam adaptation: a store-api uploadResolver for POST /{resource}/:id/file
const uploadResolver = adapter.uploadResolver(store);
// Thin pass-through of store.resourcePut(input)
// const put = adapter.upload(store);
```

### Python (`store-resource-bootstrap-py`)

```python
import asyncio
from py_store import store                                 # host store (passed in by the integrator)
from store_resource_bootstrap import capability, adapter

async def main():
    handle = capability.create(store, {
        "providers": [{"kind": "local", "options": {"root": "/data/resources"}, "priority": 0}],
        "schemas": capability.schemas(),   # default [] → registers nothing
    })
    out = await handle.start()
    # out == {"registered": ["Resource", "ResourceLocation", "ResourceBinding"], "skipped": [], "providerRegistered": []}
    # await handle.reload()

    file_resolver = adapter.download(store)
    upload_resolver = adapter.upload_resolver(store)
    # put = adapter.upload(store)   # thin pass-through of store.resource_put(**input)

asyncio.run(main())
```

## 8. Capability bootstrap

### 8.1 `capability.schemas()`

| Runtime | Signature | Returns |
|---|---|---|
| Node | `schemas()` | `Array<object>` |
| Python | `schemas()` | `list[dict]` |

Returns the built-in **optional reference** definitions for the three resource tables as a **deep copy** (mutating the returned value never affects the internal copy). The three definitions, in order, are:

| Name | `collection` | `idPrefix` | `fields` | unique index |
|---|---|---|---|---|
| `Resource` | `resources` | `""` (empty string) | `_id`, `sha1`, `fileName`, `mime`, `size`, `kind` | `{ sha1: 1 }` |
| `ResourceLocation` | `resource_locations` | `rl` | `_id`, `resourceId`, `backend`, `key`, `status`, `priority` | `{ resourceId: 1, backend: 1 }` |
| `ResourceBinding` | `resource_bindings` | `rb` | `_id`, `resourceId`, `businessTable`, `businessId`, `userId` | `{ resourceId: 1, businessTable: 1, businessId: 1 }` |

The library does **not** force-register these. Note that `Resource.idPrefix` must be the empty string — the host only generates an `_id` when `idPrefix` is truthy, so a non-empty value would break the `resourceId = sha1` convention.

### 8.2 `capability.create(store, opts)`

| Runtime | Signature | Returns |
|---|---|---|
| Node | `create(store, opts)` | `{ async start(), async reload() }` |
| Python | `create(store, opts=None)` | a `_Handle` with `async start()` / `async reload()` |

`opts` keys are **identical across runtimes (camelCase)** — see §11.

**Construction-time validation.** Any violation throws immediately when `create()` is called — the message contains the offending field / method / table / role name, and **zero façade calls** are made ("fail fast, no partial wiring"):

1. `store` must expose `register` / `has` / `configureResource` (Python: `configure_resource`).
2. `providers` must be a non-empty array; each item `{ kind: non-empty string, options?: object, priority?: int }`.
3. `url` must be an object.
4. `sign` must be a function or `null`.
5. `schema` must be an object.
6. `providerPlugins` defaults to `[]`; if given it must be an array whose items have a non-empty `kind` and a function `create`. **Only when it is non-empty** must `store` expose `registerProvider` (Python `register_provider`).
7. `schemas` defaults to `[]`; if given it must be an array (each item an object with a non-empty `name`) or `null` / `false`; an unknown top-level key also throws.
8. `fields` defaults to `undefined` (→ not passed through, host uses canonical); if given it must be an object with only known tables/roles and correctly typed values (see §12).

### 8.3 `start()` fixed sequence

`start()` runs a fixed sequence (Node; Python is isomorphic with snake_case façade names):

1. **Register `providerPlugins`** — synchronous, and **before** `configureResource`:
   `store.registerProvider(spec.kind, { create: spec.create })` (Python: `store.register_provider(spec.kind, SimpleNamespace(create=spec.create))`).
2. **Idempotently register the effective `opts.schemas`** — `has` / `register` are **synchronous** (`has(defn.name)` → push to `skipped`, else `register(defn)` → push to `registered`). With the default `[]` this step is a no-op.
3. **`await store.configureResource({ providers, url, sign, schema })`** — asynchronous (Python uses a sync/async-compatible wrapper). The `fields` key is included **only when `opts.fields` is provided**; otherwise the payload omits it, keeping the call byte-for-byte compatible with older hosts.
4. **Return** `{ registered: string[], skipped: string[], providerRegistered: string[] }` — observable, never silent.

Example return values:

```js
// fresh, with schemas: capability.schemas()
{ registered: ['Resource', 'ResourceLocation', 'ResourceBinding'], skipped: [], providerRegistered: [] }
// second start() (idempotent)
{ registered: [], skipped: ['Resource', 'ResourceLocation', 'ResourceBinding'], providerRegistered: [] }
// default (no schemas injected)
{ registered: [], skipped: [], providerRegistered: [] }
```

### 8.4 Idempotency and `reload()`

`start()` may be called repeatedly. On the first call it registers the effective `opts.schemas`; every subsequent call reports them in `skipped` with `registered` empty (`configureResource` is still called once per `start()`). `reload()` is exactly `start()` again — the host's `configure` replaces the pool wholesale, so no clearing is needed.

## 9. Adapter reference

### 9.1 `adapter.download(store, opts)`

| Runtime | Signature | Returns |
|---|---|---|
| Node | `download(store, opts = {})` | `async (req, rec, id) => { body, contentType, fileName }` |
| Python | `download(store, opts=None)` | `async (request, rec, rid) -> dict` |

This produces the store-api **`fileResolver`** contract, used by `GET /{resource}/:id/file`.

**Construction-time validation** (throws immediately): `store` must expose `resourceOpen` (Python `resource_open`); `opts` must be an object; `field`, if given, must be a non-empty string. Note a host **without** `queryOne` is fine — the resolver reads only through `resourceOpen`.

`opts`:

| Key | Type / value | Default | Notes |
|---|---|---|---|
| `field` | non-empty string | `'file'` | Name of the field on the record that carries the resource reference. Supports **dot paths** (e.g. `images.original`). A request-level `?field` overrides this. |
| `order` | array \| `undefined` | `undefined` | Hint for the order in which backends are tried when a reference is an array; defaults to the natural order. Passed to `resourceOpen(ref, { order })`. |

**Behaviour at call time** `(req, rec, id)`:

1. Resolve the field path: request-level `req.query.field` (a non-empty string) wins over the construction-time `field`.
2. Read the reference from the record by that path. A missing / empty-string / `null` reference throws a plain `Error` whose message contains the field path — **zero resource calls** are made.
3. `await store.resourceOpen(ref, order === undefined ? {} : { order })`.
4. Return `{ body: opened.bytes, contentType: opened.mime || 'application/octet-stream', fileName: opened.fileName || String(ref) }`.

The metadata (`mime` / `fileName`) comes back attached to the `resourceOpen` result — the plugin **no longer calls `queryOne`** (which is exactly why a host without `queryOne` still works). When `mime` is `null` / empty, `contentType` falls back to `application/octet-stream`; when `fileName` is `null` / empty, `fileName` falls back to the reference string.

Underlying read failure: the host throws, and the plugin **propagates it unchanged** — it never catches or rewrites.

### 9.2 `adapter.upload(store)`

| Runtime | Signature | Returns |
|---|---|---|
| Node | `upload(store)` | `async (input) => store.resourcePut(input)` |
| Python | `upload(store)` | `async (input: dict) => await store.resource_put(**input)` |

A **thin pass-through**: it does not touch the write input or output; the shape is exactly whatever the host's `resourcePut` / `resource_put` expects. Node input keys are Node-native (camelCase — e.g. `bytes`, `fileName`, `mime`, `kind`, `bind`); Python input keys are Python-native (snake_case — e.g. `bytes`, `file_name`, `mime`, `kind`, `bind`). Construction throws if `store` lacks `resourcePut` / `resource_put`.

### 9.3 `adapter.uploadResolver(store, opts)`

| Runtime | Signature | Returns |
|---|---|---|
| Node | `uploadResolver(store, opts = {})` | `async (req, rec, id) => { ref }` |
| Python | `upload_resolver(store, opts=None)` | `async (request, rec, rid) -> dict` |

This produces the store-api **`uploadResolver`** contract (symmetric to `download`), used by `POST /{resource}/:id/file`. For Node, `req.body` is the **skin-buffered `Buffer`**.

**Construction-time validation** (throws immediately): `store` must expose `resourcePut` / `resource_put`; `opts` must be an object; `kind`, if given, must be a non-empty string; `bind`, if given, must be a function.

`opts`:

| Key | Type / value | Default | Notes |
|---|---|---|---|
| `kind` | non-empty string | `'file'` | Resource category written to `Resource.kind`. |
| `bind` | function \| `null` | `null` | `(req, rec, id) => { businessTable, businessId } \| null`; returning `null` writes no `ResourceBinding`. |

**Behaviour at call time** `(req, rec, id)`:

1. Take the byte body: Node `req.body` if it is a `Buffer`; Python `await request.body()` for a Starlette request, or `request["body"]` for a dict. An empty body throws a plain `Error` (message contains "上传字节体") — **zero `resourcePut` calls** are made.
2. Build the `resourcePut` input: `{ bytes, kind }`, plus:
   - `fileName` (Node) / `file_name` (Python) — `req.query.fileName` if non-empty, else `rec.fileName` if non-empty, else omitted;
   - `mime` — `req.query.mime` if non-empty, else the `content-type` header if non-empty, else omitted;
   - `bind` — only when `bind` is a function and it returns non-null.
3. `await store.resourcePut(input)` (Python `store.resource_put(**input)`). The plugin does **no IO of its own** — the data layer does the byte write.
4. Return `{ ref }` where `ref = out.resourceId`. If `resourcePut` does not return a `resourceId`, a plain `Error` is thrown.

## 10. Providers

The optional reference `providers` namespace exposes two S3-compatible factories — `oss` and `minio` — both built on one shared base module, `s3-compat`. (The public namespace exports only `oss` and `minio`; `s3-compat` is the shared base, reachable only by deep import, and its default `kind` is `'s3'`.)

| Provider | Node module | Python module | `kind` | `forcePathStyle` | signatureVersion | Addressing rationale |
|---|---|---|---|---|---|---|
| `oss` | `src/providers/oss.js` | `providers/oss.py` | `'oss'` | `false` (virtual-hosted) | Python only: `'s3'` (V2) | OSS supports only virtual-hosted (bucket in the domain). Node uses SigV4 by default (no extra config); boto3 must use the V2 signature. |
| `minio` | `src/providers/minio.js` | `providers/minio.py` | `'minio'` | `true` (path-style) | — | A self-hosted gateway needs path-style (bucket in the path). |
| `s3-compat` (base) | `src/providers/s3-compat.js` | `providers/s3_compat.py` | `'s3'` (default) | `?? !!endpoint` (Node) / defaults to `bool(endpoint)` (Python) | — | Generic S3-compatible base; also usable for AWS. Not re-exported by the namespace index. |

**Node `oss.create(options, deps)` / `minio.create(options, deps)`** merge their preset with `options` and delegate to `s3-compat.create`. The base `create(options, deps)`:

- uses `deps` if injected, else lazily `require('@aws-sdk/client-s3')`;
- requires `options.bucket` (throws `s3-compat provider 需要 options.bucket`);
- builds a client from `options.client`, or a new `S3Client` with `{ region: options.region || 'us-east-1', endpoint: options.endpoint, forcePathStyle: options.forcePathStyle ?? !!options.endpoint, credentials: options.credentials }`;
- applies `options.prefix` to all keys (`prefix/<key>`);
- returns `{ kind, put, get, remove, exists }`.

**Python `oss.create(options, sdk)` / `minio.create(options, sdk)`** merge presets and delegate to `s3_compat.create`. The base `create(options, sdk=None)`:

- lazily `import boto3` / `from botocore.config import Config` when `sdk` is not injected;
- requires `options.bucket`;
- builds a client from `options.client`, else `sdk["client"]("s3", region_name=..., endpoint_url=..., aws_access_key_id=..., aws_secret_access_key=..., config=...)` with `addressing_style` `"path"` when path-style else `"virtual"`, plus `signature_version` when `signatureVersion` is set;
- applies `options.prefix`;
- returns `{ kind, put, get, remove, exists }` where all four are **async** (dispatched via `asyncio.to_thread`).

**Provider options (both runtimes, unless noted):**

| Option | Meaning |
|---|---|
| `bucket` | **Required.** Target bucket. |
| `region` | Region; defaults to `us-east-1`. |
| `endpoint` | S3-compatible endpoint URL. |
| `forcePathStyle` | `true` → path-style, `false` → virtual-hosted. Preset-provided; when omitted the base defaults to "path-style iff `endpoint` is set". |
| `credentials` | `{ accessKeyId, secretAccessKey }`. |
| `prefix` | Optional key prefix (`prefix/<key>`). |
| `client` | Pre-built client instance (skips client construction). |
| `signatureVersion` | Python only. `'s3'` = V2 signature (used by the OSS preset). |
| `kind` | Overrides the returned provider `kind` (presets always force their own). |

To use them, register the factory through `providerPlugins` and reference the kind in `providers`:

```js
const { capability, providers } = require('store-resource-bootstrap-node');

const handle = capability.create(store, {
  providers: [{ kind: 'oss', options: { bucket: 'reports', endpoint: 'https://oss-cn-hangzhou.aliyuncs.com' }, priority: 0 }],
  providerPlugins: [{ kind: 'oss', create: providers.oss.create }],
});
await handle.start();
```

## 11. Configuration reference

`capability.create(store, opts)` accepts a JSONC-shaped `opts` whose keys are **identical across runtimes (camelCase)**:

```jsonc
{
  "providers": [ { "kind": "local", "options": { "root": "/data/resources" }, "priority": 0 } ],
  "providerPlugins": [ { "kind": "oss", "create": "<provider factory create(options)>" } ],  // optional; default []
  "schemas": [ "<schema definitions, see spec Appendix A / capability.schemas()>" ],  // optional; default [] (registers nothing)
  "url":  { "base": "https://cdn.example.com" },  // optional; → configureResource({ url }). default {}
  "sign": null,                                    // optional; function or null. default null → configureResource({ sign })
  "schema": { "resource": "Resource", "location": "ResourceLocation", "binding": "ResourceBinding" },  // optional; defaults to the host's same names
  "fields": {                                       // optional; logical role → physical field mapping. default = canonical
    "resource": { "sha1": "sha1", "fileName": "fileName", "mime": "mime", "size": "size", "kind": "kind" },
    "location": { "resourceId": "resourceId", "backend": "backend", "key": "key", "status": "status", "priority": "priority" },
    "binding": { "resourceId": "resourceId", "businessTable": "businessTable", "businessId": "businessId", "userId": "userId" }
  }
}
```

**Exactly these seven top-level keys are allowed** — `providers`, `providerPlugins`, `schemas`, `url`, `sign`, `schema`, `fields`. Any unknown key throws an `Error` (never silently ignored).

| Key | Allowed type / value | Default | Notes |
|---|---|---|---|
| `providers` | **required**, non-empty array; each item `{ kind: non-empty string, options?: object, priority?: int }` | none (**required**) | `kind` must be a provider **already registered** on the host (`local` / `s3` built in; others supplied by the integrator, e.g. via `providerPlugins`). The plugin does **not** pre-check `kind` validity — the host throws. `priority` is an integer passed through verbatim; the backend-selection semantics belong to the host. |
| `providerPlugins` | array; each item `{ kind: non-empty string, create: function }` | `[]` | Provider factory registry: `create(options) -> provider`. **When non-empty**, the host must expose `registerProvider` (Python `register_provider`). The plugin does **not** pre-check `kind` conflicts — the host registry handles them. |
| `schemas` | array \| `null` \| `false` | `[]` | **Injection point for the schema definitions to register** (the library ships no authoritative resource schema). Array items must be objects with a non-empty string `name`, registered in order (idempotent); `null` / `false` / default → **register nothing**. Business-entity schemas are not part of this — the business owns them. |
| `url` | object | `{}` | Passed through to `configureResource` verbatim. |
| `sign` | function \| `null` | `null` | Passed through to `configureResource` verbatim. |
| `schema` | object | `{ resource: 'Resource', location: 'ResourceLocation', binding: 'ResourceBinding' }` | Three schema-name mappings; passed through to `configureResource` verbatim. |
| `fields` | object | canonical (above) | Three-table **logical role → physical field** mapping; passed through to `configureResource` verbatim (see §12). Passed through **only when provided** (default: not passed → the host uses canonical, byte-for-byte compatible). |

**`providers` is mandatory.** If it is missing or empty, `capability.create` throws before doing anything (message contains `providers`, zero façade calls). This is deliberate fail-fast.

## 12. `fields` mapping

`fields` maps each resource table's **logical role** to a **physical column name**, letting the business rename columns without touching the plugin or the generic code. It is passed to the host as `configureResource({ fields })`. Omitted tables / roles fall back to canonical names.

| Table | Required roles | Optional roles |
|---|---|---|
| `resource` | `sha1` | `fileName`, `mime`, `size`, `kind` |
| `location` | `resourceId`, `backend`, `key` | `status`, `priority` |
| `binding` | `resourceId`, `businessTable`, `businessId` | `userId` |

Validation rules (enforced at construction time, message contains the table / role name):

- unknown table → throws; unknown role within a known table → throws;
- a **required** role's value must be a **non-empty string** (`null` / `""` / non-string → throws);
- an **optional** role's value must be a non-empty string **or `null`** — `null` means "skip that column" (don't persist it);
- `_id` is **not** mappable (it is the core identity; de-duplication is by `_id`).

Example — rename `sha1`→`contentHash`, `fileName`→`name`, `mime`→`contentType`, drop `size`/`kind`; rename `backend`→`store`, `key`→`objectKey`, drop `status`; rename `businessTable`→`entity`, drop `userId`:

```jsonc
"fields": {
  "resource": { "sha1": "contentHash", "fileName": "name", "mime": "contentType", "size": null, "kind": null },
  "location": { "backend": "store", "key": "objectKey", "status": null },
  "binding": { "businessTable": "entity", "userId": null }
}
```

After `start()`, the host's `configureResource` receives exactly this object (verified by `capability.fields_passthrough`).

## 13. DDL boundary

The plugin **does not create tables**. Whether to create tables, and which ones, is up to the integrator (using the business's existing `syncSchema` (Node) / `load_defs` (Python)). `opts.schemas` only `register`s definitions into the host's schema registry (so that `configureResource`'s `schema` name mappings can reference them) — it **never triggers DDL**.

## 14. Error mapping

| Situation | Plugin behaviour |
|---|---|
| `download` — record lacks the reference field, or the reference is empty | throws a plain **`Error`** (Chinese message, **no `ERR_` prefix**) |
| `uploadResolver` — request body is empty, or `resourcePut` did not return a `resourceId` | throws a plain **`Error`** (Chinese message, **no `ERR_` prefix**) |
| `capability.create` — invalid config (unknown top-level key / wrong type / missing façade method / `fields` unknown table or role, or a required role that is not a non-empty string) | throws an `Error` whose message contains the field / method / table / role name |
| `resourceOpen` — not found, or the underlying read fails | the host throws; the plugin **propagates it unchanged, never catches or rewrites** |

- The plugin produces **no** HTTP status code / error name (`404` / `NOT_FOUND` / `ERR_*` / `500` are all forbidden in the plugin source; the conformance machine check enforces this).
- The download semantics "record does not exist or `fileField` is empty → `404 NOT_FOUND`" belong to the **existing store-api skin** — not this plugin.
- Cross-runtime note: the thrown class is `Error` in Node and `ValueError` in Python; both runtimes' tests assert on the message substring, not the class name.

## 15. Scenarios

Each scenario follows the same four-part shape: **Business context → Config / calls → Result → Why it is an advantage.**

### Scenario 1 — Avatar upload in local / dev (minio or `s3-compat`, path-style)

- **Business context.** A user-profile service lets users upload an avatar. In local / dev there is no cloud bucket, only a self-hosted MinIO (or any path-style S3-compatible gateway).
- **Config / calls.**
  ```js
  const { capability, adapter, providers } = require('store-resource-bootstrap-node');

  const handle = capability.create(store, {
    providers: [{
      kind: 'minio',
      options: { bucket: 'avatars', endpoint: 'http://minio:9000', prefix: 'users' },
      priority: 0,
    }],
    providerPlugins: [{ kind: 'minio', create: providers.minio.create }],
    schemas: capability.schemas(),   // register the three optional reference tables
  });
  await handle.start();

  const uploadResolver = adapter.uploadResolver(store, { kind: 'avatar' });
  // wire uploadResolver into store-api's POST /{resource}/:id/file
  ```
- **Result.** `start()` returns `{ registered: ['Resource','ResourceLocation','ResourceBinding'], skipped: [], providerRegistered: ['minio'] }`. The minio preset forces `forcePathStyle: true`, so the client addresses the bucket in the path (`http://minio:9000/avatars/...`). An upload of `Body: <bytes>` with `ContentType` from `req.query.mime` is written to the data layer via `resourcePut`.
- **Why it is an advantage.** The same `store-api` seam is used in dev and prod; only the `providers` entry changes. Self-hosted MinIO works out of the box through the `forcePathStyle` preset — no custom storage adapter, no conditional branching in business code, no new HTTP route.

### Scenario 2 — Report attachment download from OSS (virtual-hosted)

- **Business context.** A reporting service stores generated report attachments in Alibaba Cloud OSS and lets users download them.
- **Config / calls.**
  ```js
  const handle = capability.create(store, {
    providers: [{
      kind: 'oss',
      options: { bucket: 'reports', endpoint: 'https://oss-cn-hangzhou.aliyuncs.com', prefix: 'export' },
      priority: 0,
    }],
    providerPlugins: [{ kind: 'oss', create: providers.oss.create }],
  });
  await handle.start();

  const fileResolver = adapter.download(store, { field: 'file' });
  // wire fileResolver into store-api's GET /{resource}/:id/file
  ```
- **Result.** The OSS preset forces `forcePathStyle: false` (virtual-hosted, bucket in the domain). A `GET /{resource}/:id/file` on a record like `{ file: 'ref1' }` results in one `resourceOpen('ref1', {})` and returns `{ body, contentType, fileName }` to the skin. If the host returns `mime: null`, `contentType` falls back to `application/octet-stream`.
- **Why it is an advantage.** The OSS-specific addressing requirement (virtual-hosted only) is encapsulated in the preset — the business never has to know about path-style vs virtual-hosted. On Node, SigV4 works with no extra configuration; on Python, the OSS preset supplies the required V2 signature automatically.

### Scenario 3 — Multiple providers coexisting, dispatched per use (via `order`)

- **Business context.** One service keeps small, hot avatars on a local backend while archiving large reports on remote object storage. Reads should prefer the right backend depending on the use.
- **Config / calls.**
  ```js
  const handle = capability.create(store, {
    providers: [
      { kind: 'local', options: { root: '/data/resources' }, priority: 1 },
      { kind: 'oss', options: { bucket: 'reports' }, priority: 0 },
    ],
  });
  await handle.start();

  // Report download: prefer the OSS backend
  const reportResolver = adapter.download(store, { order: ['oss'] });
  // Avatar download: prefer the local backend
  const avatarResolver = adapter.download(store, { order: ['local'] });
  ```
- **Result.** The whole `providers` array is passed to `configureResource` verbatim, building one resource pool. At read time the `order` hint is forwarded to `resourceOpen(ref, { order })` — e.g. the report resolver issues `resourceOpen('ref', { order: ['oss'] })` and the local resolver issues `resourceOpen('ref', { order: ['local'] })`.
- **Why it is an advantage.** Multiple storage backends share a single, uniform download seam; the "which backend" decision is a per-resolver `order` hint rather than hard-coded branching. The plugin stays out of the ranking semantics — it forwards the hint and lets the host's resource capability decide.

### Scenario 4 — Assembling `url` / `sign` (URL base and signing seam)

- **Business context.** Resource URLs must be handed out through a CDN base, and links may need to be signed. URL composition and signing are policy owned by the host/business.
- **Config / calls.**
  ```js
  const handle = capability.create(store, {
    providers: [{ kind: 'oss', options: { bucket: 'assets' } }],
    url: { base: 'https://cdn.example.com' },
    sign: (resource) => mySigner(resource),
  });
  await handle.start();
  ```
- **Result.** `start()` passes `url` and `sign` through to `store.configureResource` **verbatim** (as `{ url: { base: 'https://cdn.example.com' }, sign: <fn> }`); the host's resource capability owns URL composition/signing. If `url` / `sign` are omitted, the defaults `{}` / `null` are forwarded.
- **Why it is an advantage.** The plugin is a pure config conduit — the CDN base and signing strategy can be swapped or extended without any plugin change, and the plugin never re-implements URL logic (URL composition is sunk to core, the plugin implements none of it).
- **Explicitly not covered here:** presigned-URL direct upload that bypasses the data layer is **not** provided by this plugin — uploads always go through the host's `resourcePut` (see §16/§17).

### Scenario 5 — Renaming physical columns via `fields` without touching business code

- **Business context.** The business already owns resource tables with non-canonical column names (e.g. `contentHash`, `objectKey`, `entity`). It wants the generic upload/download code to work against them unchanged.
- **Config / calls.**
  ```js
  const handle = capability.create(store, {
    providers: [{ kind: 'local', options: { root: '/data/resources' } }],
    fields: {
      resource: { sha1: 'contentHash', fileName: 'name', mime: 'contentType', size: null, kind: null },
      location: { backend: 'store', key: 'objectKey', status: null },
      binding: { businessTable: 'entity', userId: null },
    },
  });
  await handle.start();
  ```
- **Result.** `configureResource` receives exactly the `fields` object above. The plugin validates only the **shape** (unknown table / role, required-role type, optional-role type) and passes it through; the semantic adjudication happens in the host. `size` / `kind` / `status` / `userId` mapped to `null` are not persisted.
- **Why it is an advantage.** The logical-to-physical mapping lives entirely in configuration — business data models are never coupled into the generic library, and a column rename is a one-line config change with zero code change. The `null` convention lets a deployment drop columns it does not use.

### Scenario 6 — Missing `providers` fails loudly at construction

- **Business context.** A misconfigured deployment forgets to supply the resource pool. The integrator wants to know immediately, not on the first request.
- **Config / calls.**
  ```js
  capability.create(store, {});                     // throws
  capability.create(store, { providers: [] });      // throws
  ```
- **Result.** Both calls throw an error whose message contains `providers` — **before any façade call** (zero `register` / `has` / `configureResource` invocations). Likewise an unknown top-level key, a bad `kind` / `options` / `priority`, a bad `url` / `sign` / `schema`, a malformed `schemas`, or a malformed `fields` all throw at construction and make zero façade calls.
- **Why it is an advantage.** Fail-fast validation surfaces configuration errors at wiring time, not under load. Because construction is validated before any host interaction, a bad config can never leave a half-wired pool behind.

### Scenario 7 — Cooperating with the store-api file sub-route

- **Business context.** The skin (`store-api`) already exposes the resource byte sub-route `GET` / `POST /{resource}/:id/file`. The business wants bytes to flow through it without writing a new route.
- **Config / calls.**
  ```js
  const { capability, adapter } = require('store-resource-bootstrap-node');

  await capability.create(store, {
    providers: [{ kind: 'local', options: { root: '/data/resources' } }],
  }).start();

  const fileResolver = adapter.download(store);          // for GET  /{resource}/:id/file
  const uploadResolver = adapter.uploadResolver(store);  // for POST /{resource}/:id/file
  // pass both into the store-api skin wiring
  ```
- **Result.** `GET /{resource}/:id/file` calls `fileResolver(req, rec, id)` and returns the byte stream with `content-type` / `content-disposition` (non-JSON); an absent/empty reference becomes the skin's `404 NOT_FOUND`. `POST /{resource}/:id/file` calls `uploadResolver(req, rec, id)`, relays bytes through `resourcePut`, and returns `{ ref }` so the skin can write the reference back to the record.
- **Why it is an advantage.** The plugin adds no HTTP route and no status code of its own — it plugs into the existing seam symmetrically (download and upload have the same `(req, rec, id)` shape), so the skin stays a pure transporter and the business writes zero HTTP code.

## 16. Customisation / extension points

- **Bring your own provider.** Implement a factory `create(options) -> provider` and register it via `providerPlugins`; then reference its `kind` in `providers`. The plugin registers each factory on the host through `registerProvider` (Python `register_provider`) **before** `configureResource`, and reports registered kinds in `start()`'s `providerRegistered`. When `providerPlugins` is non-empty, the host must expose that façade.
  ```js
  const myProvider = {
    kind: 'my-store',
    create: (options) => ({ /* put / get / remove / exists */ }),
  };
  capability.create(store, {
    providers: [{ kind: 'my-store', options: { /* ... */ } }],
    providerPlugins: [{ kind: 'my-store', create: myProvider.create }],
  });
  ```
- **Use the shipped S3-compatible base directly.** Both `oss` and `minio` are thin presets over the shared `s3-compat` base. If you need a bare S3-compatible provider with the default `kind: 's3'`, deep-import the base (`src/providers/s3-compat` (Node) / `providers.s3_compat` (Python)) and call its `create`. It is deliberately **not** part of the public `providers` namespace (which exports only `oss` and `minio`).
- **Bring your own schemas.** `opts.schemas` is a generic injection point: pass your own definitions (they are deep-copied and registered in order), or `null` / `false` / nothing to register zero tables.
- **Reshape the resource tables.** `opts.fields` remaps logical roles to physical column names (see §12), so your existing schema can be reused as-is.

## 17. Boundaries and non-goals

- **No DDL.** The plugin never creates tables (§13).
- **No HTTP routes, no status codes, no error names.** HTTP exposure lives solely in the `store-api` skin; the plugin throws plain `Error` / `ValueError`.
- **No host / core imports.** The store instance is always passed in; the plugin imports nothing from a host, skin, or core package.
- **No SHA-1 / content addressing / URL composition.** These are sunk into core; the plugin implements none of them.
- **No direct-to-storage presigned upload.** Uploads always go through the host's `resourcePut` (`adapter.upload` is a thin pass-through; `adapter.uploadResolver` relays through `resourcePut`). The plugin does not generate presigned URLs.
- **First-wave scope.** Included: optional reference schemas with opt-in registration and seam adaptation for **Node / Python**. Explicitly excluded in this phase (with rationale):

  | Excluded | Rationale |
  |---|---|
  | Admin plane | reuses store-api's existing CRUD — an enhancement, not a prerequisite |
  | Resource-list HTTP plane | reuses store-api's existing surface |
  | `go` runtime | first wave is Node / Python only (per the per-end contract table) |
  | `store-api` rust | first wave is Node / Python only |
  | Other skins (GraphQL / gRPC) | the resource capability is a **host side-path**; HTTP exposure lives only in store-api |

  "Excluded" is not "unsupported": inclusion anchors are go-ecosystem maturity and the gateway switch; no code is reserved in this phase.

## 18. FAQ

**Q1. Does the plugin create the resource tables for me?**
No. It never runs DDL. `capability.schemas()` only *returns* the optional reference definitions; `opts.schemas` only `register`s them into the host schema registry. Creating tables is up to you (the business's existing `syncSchema` (Node) / `load_defs` (Python)).

**Q2. What happens if I omit `providers`?**
`capability.create` throws immediately with a message containing `providers`, making zero façade calls. `providers` is the only required key.

**Q3. What are the seven allowed config keys?**
`providers`, `providerPlugins`, `schemas`, `url`, `sign`, `schema`, `fields`. Any other top-level key throws.

**Q4. Do I have to use `capability.schemas()`?**
No. `schemas` defaults to `[]` (register nothing). You can pass the built-in optional reference set, your own definitions, or `null` / `false` to register nothing.

**Q5. Does `download` need a `queryOne` façade on the host?**
No. `download` reads bytes **and** metadata (`fileName` / `mime`) through `resourceOpen` alone; a host without `queryOne` works fine. When the returned `mime` / `fileName` is `null`, the resolver falls back to `application/octet-stream` / the reference string.

**Q6. Which column of a reference does `download` read?**
By default the record field named `file`. Override it with `opts.field` (supports dot paths like `images.original`), or per request with `?field`, which wins over the construction-time `field`.

**Q7. How do I rename the resource-table columns?**
Use `opts.fields` to map logical role → physical column name (see §12). Required roles must be non-empty strings; optional roles may be a non-empty string or `null` (skip the column). `_id` is not mappable.

**Q8. Are `oss` and `minio` real implementations or just aliases?**
Both are real S3-compatible implementations built on the shared `s3-compat` base. `oss` forces virtual-hosted (`forcePathStyle: false`) and, on Python, the V2 signature; `minio` forces path-style (`forcePathStyle: true`).

**Q9. Do I need to install `@aws-sdk/client-s3` / `boto3`?**
Only if you actually use the `oss` / `minio` providers. They are optional and lazily loaded — the package imports and the `capability` / `adapter` namespaces work without them; only calling a provider's `create()` throws.

**Q10. Does the plugin generate presigned URLs for direct upload?**
No. Uploads go through the host's `resourcePut` (`adapter.upload` is a thin pass-through; `adapter.uploadResolver` relays through `resourcePut`). Presigned direct upload is a non-goal.

**Q11. Is `start()` safe to call twice?**
Yes. It is idempotent: on the first call the effective `schemas` are `registered`; on later calls they are reported in `skipped` and `registered` is empty. `configureResource` is called once per `start()`. `reload()` is exactly `start()` again.

**Q12. Which error class is thrown?**
`Error` in Node, `ValueError` in Python. The messages are plain (no `ERR_` prefix, no status codes); both runtimes' tests assert on the message substring.

## 19. Development

```bash
# Node: unit tests + conformance cases
cd node && npm i && npm test          # runs `node --test`

# Python: unit tests + conformance cases
cd py && pip install -e ".[dev]" && pytest
```

**Pipeline.** The spec is the single source of truth → both runtimes implement from it → [`conformance/cases.json`](./conformance/cases.json) is loaded by **both** runtimes as the shared parity corpus (the expected values are never duplicated per runtime). A machine check embedded in each runtime's test suite freezes the published source against forbidden literals (`404` / `NOT_FOUND` / `ERR_` / `500`), forbidden host references (`require('nodejs-store')` / `from py_store`), and forbidden calls (`createHash` / `hashlib` / `resourceComposeUrl`).

## 20. Related projects

| Project | Relationship |
|---|---|
| [`nodejs-store`](../nodejs-store) | Node host; owns the resource capability this plugin configures (`configureResource`, `resourceOpen`, `resourcePut`) |
| [`py-store`](../py-store) | Python host (isomorphic to `nodejs-store`) |
| [`store-api`](../store-api) | The skin whose `fileResolver` / `uploadResolver` seams this plugin fills; exposes `GET` / `POST /{resource}/:id/file` |
| [`store-rbac-bootstrap`](../store-rbac-bootstrap) | The plugin pattern this package mirrors (read config → hook into existing seams) |

## 21. License

MIT. Copyright (c) 2026 丁滔 (see [`LICENSE`](./LICENSE)). Both packages declare `MIT` — see `node/package.json` (`"license": "MIT"`) and `py/pyproject.toml` (`license = { text = "MIT" }`).

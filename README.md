# store-resource-bootstrap

Optional **resource bootstrap plugin** for the common-store data-layer family (hosts [nodejs-store](../nodejs-store) / [py-store](../py-store)):

| Concern | Host package | Seam |
|---|---|---|
| Capability bootstrap | nodejs-store (node / py) | `register` / `has` / `configureResource` (`configure_resource`) |
| Seam adaptation | store-api (node / py) | `fileResolver` / `file_resolver` (GET `/{resource}/:id/file`) |

> 中文说明：[README.zh-CN.md](./README.zh-CN.md)

## 1. Positioning

The plugin does exactly two things and nothing else:

1. **Capability bootstrap** — register the caller-**injected** schema definitions (`schemas`, optional; nothing is registered by default) and call the host store's existing `configureResource({ providers, url, sign, schema, fields })`;
2. **Seam adaptation** — produce a store-api `fileResolver` (thin read-through) and a thin pass-through `resourcePut`.

**Schema ownership**: the library ships **no authoritative resource schema** — business-entity schemas (e.g. `product.images` / `user.avatar`) are defined by the business layer and never touched here; the three resource tables (`Resource` / `ResourceLocation` / `ResourceBinding`, the persistence model of the resource capability itself) are provided only as an **optional reference** (`capability.schemas()`), and whether to register them is decided by `opts.schemas` (default: register nothing). The **column structure of the three resource tables is likewise business-definable**: their column names are not hard-coded in the host, but declared by the integrator via the `opts.fields` "logical role → physical field" mapping (default = canonical column names). The library only encapsulates the **generic code** for upload / download / storage — field naming and structure belong to the business layer, so the business data model is never coupled into the generic library.

Three invariants: **zero semantic invention**, **zero host dependency**, **zero regression**. The plugin never `require`s / imports any host, skin or core package (**no third-party runtime dependencies by default**; the optional reference provider modules `oss` / `minio` need an S3-compatible SDK, declared as **optional dependencies** and **lazily loaded** — when not installed, the module still loads and `capability` / `adapter` and tests are unaffected; only actually calling that module's `create()` throws), never invents error prefixes or status codes (it throws plain errors), and never touches any sibling repository. It is exposed as two namespaces `capability` and `adapter`, and additionally ships an **optional reference provider namespace** `providers` (`oss` / `minio`, S3-compatible presets; SDK lazily loaded) for integrators to reference directly in `providerPlugins`. The single source of truth is [`spec/00-protocol.md`](./spec/00-protocol.md).

## 2. Quick start

### Node (`store-resource-bootstrap-node`)

```js
const { init, store } = require('nodejs-store');       // host store (provided by the integrator)
const { capability, adapter } = require('store-resource-bootstrap-node');

// capability bootstrap: inject schema definitions as needed (here the built-in reference set) + configure the resource pool
const handle = capability.create(store, {
  providers: [{ kind: 'local', options: { root: '/data/resources' }, priority: 0 }],
  schemas: capability.schemas(),  // default registers nothing; the business may pass its own definitions
});
await handle.start();
// await handle.reload();  // re-run start() (host keeps the pools swapped atomically)

// seam adaptation: a store-api fileResolver (GET /{resource}/:id/file)
const fileResolver = adapter.download(store);
// const put = adapter.upload(store);  // thin pass-through of store.resourcePut(input)
```

### Python (`store-resource-bootstrap-py`)

```python
import asyncio
from py_store import init, store                        # host store (provided by the integrator)
from store_resource_bootstrap import capability, adapter

async def main():
    handle = capability.create(store, {
        "providers": [{"kind": "local", "options": {"root": "/data/resources"}, "priority": 0}],
        "schemas": capability.schemas(),  # default registers nothing; the business may pass its own definitions
    })
    await handle.start()
    # await handle.reload()

    file_resolver = adapter.download(store)
    # put = adapter.upload(store)  # thin pass-through of store.resource_put(**input)

asyncio.run(main())
```

## 3. Config shape

```jsonc
{
  "providers": [ { "kind": "local", "options": { "root": "/data/resources" }, "priority": 0 } ],
  "providerPlugins": [ { "kind": "oss", "create": "<provider factory create(options)>" } ],  // optional; default []
  "schemas": [ "<schema definitions, see spec Appendix A / capability.schemas()>" ],  // optional; default [] (registers nothing)
  "url":  { "base": "https://cdn.example.com" },  // optional; → configureResource({url}). default {}
  "sign": null,                                    // optional; function or null. default null → configureResource({sign})
  "schema": { "resource": "Resource", "location": "ResourceLocation", "binding": "ResourceBinding" },  // optional; defaults to the host's same names
  "fields": {                                       // optional; logical role → physical field mapping. default = canonical
    "resource": { "sha1": "sha1", "fileName": "fileName", "mime": "mime", "size": "size", "kind": "kind" },
    "location": { "resourceId": "resourceId", "backend": "backend", "key": "key", "status": "status", "priority": "priority" },
    "binding": { "resourceId": "resourceId", "businessTable": "businessTable", "businessId": "businessId", "userId": "userId" }
  }
}
```

| Field | Allowed type / value | Default | Notes |
|---|---|---|---|
| `providers` | **required**, non-empty array; each item `{kind: non-empty string, options?: object, priority?: int}` | none (required) | `kind` must be a provider **already registered** on the host (`local` / `s3` built in; others supplied by the integrator). The plugin does **not** pre-check `kind` validity — the host throws |
| `providerPlugins` | array; each item `{kind: non-empty string, create: function}` | `[]` | provider factory registry; `create(options) -> provider`. **When non-empty**, the host must expose `registerProvider` (py `register_provider`). The plugin does **not** pre-check `kind` conflicts — the host registry handles them |
| `schemas` | array \| `null` \| `false` | `[]` | **injection point for schema definitions to register** (the library ships no authoritative resource schema). Array items must be objects with a non-empty string `name`, registered in order (idempotent); `null` / `false` / default → **register nothing**. Business-entity schemas are not part of this — the business owns them |
| `url` | object | `{}` | passed through to `configureResource` verbatim |
| `sign` | function \| `null` | `null` | passed through to `configureResource` verbatim |
| `schema` | object | `{resource:'Resource',location:'ResourceLocation',binding:'ResourceBinding'}` | three schema-name mappings; passed through to `configureResource` verbatim |
| `fields` | object | canonical (above) | three-table **logical role → physical field** mapping; passed through to `configureResource({fields})` verbatim, letting the business define the resource-table column structure. Validation: unknown table / unknown role → throws; **required roles** (`resource.sha1`, `location.resourceId`/`backend`/`key`, `binding.resourceId`/`businessTable`/`businessId`) must be non-empty strings; **optional roles** are a non-empty string or `null` (`null` = skip that column). `_id` is not mappable (core identity; dedup is by `_id`). Passed through **only when provided** (default: not passed → host uses canonical, byte-for-byte compatible) |

Only the seven top-level keys above are allowed; any unknown key is a config error (throws, never silently ignored). See [`spec/00-protocol.md`](./spec/00-protocol.md) §Config shape / §Bootstrap rules for the full contract. The DDL boundary: the plugin **does not create tables** — whether/how to create tables is up to the integrator (its existing `syncSchema` (node) / `load_defs` (py)); `schemas` only `register`s definitions into the host schema registry and never triggers DDL.

## 4. Per-end contract table

| Capability · Runtime | Signature | Return / semantics |
|---|---|---|
| `capability.schemas` · node | `schemas()` | `Array<object>`: the built-in **optional reference** definitions (the three tables, **deep-copied**; caller mutation does not affect the internal copy; the library does not force-register them) |
| `capability.schemas` · py | `schemas()` | `list[dict]` (as above, deep-copied) |
| `capability.create` · node | `create(store, opts)` | `{ async start(), async reload() }` |
| `capability.create` · py | `create(store, opts=None)` | `_Handle` with `async start()` / `async reload()`; `opts` keys are **identical** to node (camelCase: `providers`/`providerPlugins`/`schemas`/`url`/`sign`/`schema`/`fields`) |
| `adapter.download` · node | `download(store, opts = {})` → `async (req, rec, id) => {body, contentType, fileName}` | store-api `fileResolver` contract; **camelCase keys** (aligned with `store-api/node` existing reads). Bytes + metadata come from `resourceOpen` alone; `contentType` / `fileName` fall back when the returned `mime` / `fileName` is `null` (the plugin no longer calls `queryOne`) |
| `adapter.download` · py | `download(store, opts=None)` → `async (request, rec, rid) -> dict` | store-api py `file_resolver` contract; `opts` keys same as node (`field` / `order`); **camelCase keys** (aligned with `store-api/py`'s `out.get("contentType")` / `out.get("fileName")`). Same as node: reads only via `resource_open`, no `query_one` |
| `adapter.upload` · node | `upload(store)` → `async (input) => store.resourcePut(input)` | thin pass-through, does not touch the write input/output |
| `adapter.upload` · py | `upload(store)` → `async (input: dict) => await store.resource_put(**input)` | thin pass-through; `input` keys are py-native (`file_name` / `mime` / `kind` / `bind` / `bytes`) |

`start()` runs a fixed sequence (node; py is isomorphic with snake_case facade names): ① register `providerPlugins` (**synchronous**, before `configureResource`), ② idempotently register the effective `opts.schemas` set (`has`/`register` are **synchronous**; default `[]` → this step is a no-op), ③ `await store.configureResource({ providers, url, sign, schema, fields })` (**asynchronous**; `fields` included **only when provided**), ④ return `{ registered: string[], skipped: string[], providerRegistered: string[] }` (observable, never silent). `reload()` ≡ runs `start()` again.

## 5. First-wave scope and exclusions

Included: optional reference schemas with opt-in registration + seam adaptation for both runtimes (node / py).

Explicitly **excluded** in this phase (with rationale):

| Excluded | Rationale |
|---|---|
| Admin plane | reuses store-api's existing CRUD — an enhancement, not a prerequisite |
| Resource-list HTTP plane | reuses store-api's existing surface |
| go runtime | first wave is node / py only (per the per-end contract table) |
| store-api rust | first wave is node / py only (per the per-end contract table) |
| Other skins (GraphQL / gRPC) | the resource capability is a **host side-path**; HTTP exposure lives only in store-api, so exposing a resource plane in another skin is that skin's own concern |

"Excluded" is not "unsupported": inclusion anchors are the go ecosystem maturity and the gateway switch; no code is reserved in this phase.

## 6. Development and testing

```bash
node: cd node && npm i && npm test                 # unit + conformance cases
py:   cd py && pip install -e ".[dev]" && pytest  # unit + conformance cases
```

Pipeline: **spec is the single source of truth** → both runtimes implement from it → `conformance/cases.json` is loaded by both runtimes as the shared parity corpus (no per-runtime duplicated expectations).

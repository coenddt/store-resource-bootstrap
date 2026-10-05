# store-resource-bootstrap

Optional **resource bootstrap plugin** for the common-store data-layer family (hosts [nodejs-store](../nodejs-store) / [py-store](../py-store)):

| Concern | Host package | Seam |
|---|---|---|
| Capability bootstrap | nodejs-store (node / py) | `register` / `has` / `configureResource` (`configure_resource`) |
| Seam adaptation | store-api (node / py) | `fileResolver` / `file_resolver` (GET `/{resource}/:id/file`) |

> 中文说明：[README.zh-CN.md](./README.zh-CN.md)

## 1. Positioning

The plugin does exactly two things and nothing else:

1. **Capability bootstrap** — register the three schemas `Resource` / `ResourceLocation` / `ResourceBinding` and call the host store's existing `configureResource({ providers, url, sign, schema })`;
2. **Seam adaptation** — produce a store-api `fileResolver` (thin read-through) and a thin pass-through `resourcePut`.

Three invariants: **zero semantic invention**, **zero host dependency**, **zero regression**. The plugin never `require`s / imports any host, skin or core package (and has no third-party runtime dependencies), never invents error prefixes or status codes (it throws plain errors), and never touches any sibling repository. It is exposed as two namespaces: `capability` and `adapter`. The single source of truth is [`spec/00-protocol.md`](./spec/00-protocol.md).

## 2. Quick start

### Node (`store-resource-bootstrap-node`)

```js
const { init, store } = require('nodejs-store');       // host store (provided by the integrator)
const { capability, adapter } = require('store-resource-bootstrap-node');

// capability bootstrap: register the three schemas + configure the resource pool
const handle = capability.create(store, {
  providers: [{ kind: 'local', options: { root: '/data/resources' }, priority: 0 }],
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
  "url":  { "base": "https://cdn.example.com" },  // optional; → configureResource({url}). default {}
  "sign": null,                                    // optional; function or null. default null → configureResource({sign})
  "schema": { "resource": "Resource", "location": "ResourceLocation", "binding": "ResourceBinding" }  // optional; defaults to the host's same names
}
```

| Field | Allowed type / value | Default | Notes |
|---|---|---|---|
| `providers` | **required**, non-empty array; each item `{kind: non-empty string, options?: object, priority?: int}` | none (required) | `kind` must be a provider **already registered** on the host (`local` / `s3` built in; others supplied by the integrator). The plugin does **not** pre-check `kind` validity — the host throws |
| `url` | object | `{}` | passed through to `configureResource` verbatim |
| `sign` | function \| `null` | `null` | passed through to `configureResource` verbatim |
| `schema` | object | `{resource:'Resource',location:'ResourceLocation',binding:'ResourceBinding'}` | three schema-name mappings; passed through to `configureResource` verbatim |

Only the four top-level keys above are allowed; any unknown key is a config error (throws, never silently ignored). See [`spec/00-protocol.md`](./spec/00-protocol.md) §Config shape / §Bootstrap rules for the full contract. The DDL boundary: the plugin **does not create tables** — the three schemas' DDL is covered by the integrator's existing `syncSchema` (node) / `load_defs` (py).

## 4. Per-end contract table

| Capability · Runtime | Signature | Return / semantics |
|---|---|---|
| `capability.schemas` · node | `schemas()` | `Array<object>` (the three tables, **deep-copied**; caller mutation does not affect the internal copy) |
| `capability.schemas` · py | `schemas()` | `list[dict]` (as above, deep-copied) |
| `capability.create` · node | `create(store, opts)` | `{ async start(), async reload() }` |
| `capability.create` · py | `create(store, opts=None)` | `_Handle` with `async start()` / `async reload()`; `opts` keys are **identical** to node (camelCase: `providers`/`url`/`sign`/`schema`) |
| `adapter.download` · node | `download(store, opts = {})` → `async (req, rec, id) => {body, contentType, fileName}` | store-api `fileResolver` contract; **camelCase keys** (aligned with `store-api/node` existing reads) |
| `adapter.download` · py | `download(store, opts=None)` → `async (request, rec, rid) -> dict` | store-api py `file_resolver` contract; `opts` keys same as node (`field` / `order`); **camelCase keys** (aligned with `store-api/py`'s `out.get("contentType")` / `out.get("fileName")`) |
| `adapter.upload` · node | `upload(store)` → `async (input) => store.resourcePut(input)` | thin pass-through, does not touch the write input/output |
| `adapter.upload` · py | `upload(store)` → `async (input: dict) => await store.resource_put(**input)` | thin pass-through; `input` keys are py-native (`file_name` / `mime` / `kind` / `bind` / `bytes`) |

`start()` runs a fixed sequence (node; py is isomorphic with snake_case facade names): ① idempotently register each table (`has`/`register` are **synchronous**), ② `await store.configureResource({ providers, url, sign, schema })` (**asynchronous**), ③ return `{ registered: string[], skipped: string[] }` (observable, never silent). `reload()` ≡ runs `start()` again.

## 5. First-wave scope and exclusions

Included: three-schema bootstrap + seam adaptation for both runtimes (node / py).

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

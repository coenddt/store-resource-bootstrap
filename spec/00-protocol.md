# 00 — 资源引导插件包：引导协议

> 唯一事实源：02（node）/ 03（py）两端的一切字段名、取值、签名一律回指本文件，不得另立口径。
> 日期：2026-10-05
> 上游依据：`doc/execution/2026/10/已完成-资源数据驱动-02/03/04-*.md`（宿主资源能力 / 三 schema / 皮下载端点）。

## 定位

`store-resource-bootstrap` 属于 common-store「插件 / 胶水」层（**非协议皮、非宿主、非 core**），形态复刻 `store-rbac-bootstrap`（读配置 → 挂接既有接缝），只做两件事：

1. **能力引导**：把资源三 schema 注册进宿主 store（`register`，幂等），并把 `providers` / `url` / `sign` / `schema` 装配给宿主既有资源门面 `configureResource`；
2. **接缝适配**：产出皮肤下载所需的 `fileResolver`（`download`）与薄透传的 `resourcePut`（`upload`）。

显式声明**双命名空间**：

- `capability`：能力引导（`schemas` / `create`）；
- `adapter`：接缝适配（`download` / `upload`）。

三条铁律：

- **零语义发明**：插件不产生任何 HTTP 状态码 / 错误名 / 错误前缀，只抛普通 `Error`（下载 404 语义由 store-api 皮既有实现承担）；
- **零宿主依赖**：不 `require('nodejs-store')`、不 `import py_store`，不依赖任何 core / 皮肤包；宿主实例由接入方作为参数传入；
- **零回归**：不修改任何既有子仓（`nodejs-store` / `py-store` / `rust-store` / `store-api` / `store-rbac-bootstrap` 等），纯增量。

复用既有接缝：下载走 store-api 既有 `GET /{resource}/:id/file`（皮既有 `fileResolver` / `file_resolver` 接缝）；上传走接入方既有写端点（`resourcePut` / `resource_put`）。插件**不建 HTTP 路由、不建表 DDL**。

## 配置形状（node / py 同构）

`capability.create(store, opts)` 的 `opts` 为 JSONC 形状（node / py 键名**同构 camelCase**）：

```jsonc
{
  "providers": [ { "kind": "local", "options": { "root": "/data/resources" }, "priority": 0 } ],
  "url":  { "base": "https://cdn.example.com" },  // 可选；→ configureResource({url})。缺省 {}
  "sign": null,                                    // 可选；函数或 null。缺省 null → configureResource({sign})
  "schema": { "resource": "Resource", "location": "ResourceLocation", "binding": "ResourceBinding" }  // 可选；缺省宿主同名
}
```

| 字段 | 允许类型 / 取值 | 缺省 | 备注 |
|---|---|---|---|
| `providers` | **必填**，非空数组；每项 `{kind: 非空字符串, options?: 对象, priority?: 整数}` | 无（必填） | `kind` 须为宿主**已注册**的 provider（`local` / `s3` 内置；其余由接入方经宿主自备）。插件**不预检** kind 有效性，交宿主抛错 |
| `url` | 对象 | `{}` | 原样传 `configureResource` |
| `sign` | 函数 \| `null` | `null` | 原样传 `configureResource` |
| `schema` | 对象 | `{resource:'Resource',location:'ResourceLocation',binding:'ResourceBinding'}` | 三 schema 名映射；原样传 `configureResource` |

- 顶层**仅允许** `providers` / `url` / `sign` / `schema` 四个键；出现未知键 → 抛 `Error`（禁静默忽略，对齐 no-error-masking）。

`adapter.download(store, opts)` 的 `opts`：

| 字段 | 允许类型 / 取值 | 缺省 | 备注 |
|---|---|---|---|
| `field` | 非空字符串 | `'file'` | 记录上承载资源引用的字段名 |
| `order` | 数组 \| `undefined` | `undefined` | 引用为数组时的取值顺序提示；缺省按原序 |

## 引导规则

### 入口

```js
const { capability, adapter } = require('store-resource-bootstrap-node');
```

```python
from store_resource_bootstrap import capability, adapter
```

### `start()` 固定序列（node；py 同构，门面名 snake_case）

1. 逐表幂等注册（`has` / `register` **同步**调用，无 `await`）：
   `for (const defn of schemas()) { store.has(defn.name) ? skipped.push(defn.name) : (store.register(defn), registered.push(defn.name)) }`
2. `await store.configureResource({ providers, url, sign, schema })`（**异步**；py 用 sync / async 兼容包装）；
3. 返回 `{ registered: string[], skipped: string[] }`（可观测，禁静默）。

### `reload()` 固定序列

≡ 再跑一次 `start()`（宿主 `configure` 为整体替换 `_pool`，无需先清除）。

### 构造期校验

`capability.create` 内，任一不符抛 `Error`（消息含字段名）：

1. `store` 具 `register` / `has` / `configureResource`（py `configure_resource`）；
2. `providers` 为非空数组，逐项按「配置形状」校验（`kind` 非空字符串、`options` 对象、`priority` 整数）；
3. `url` 为对象；
4. `sign` 为函数或 `null`；
5. `schema` 为对象。

### 幂等

`start()` 可重复调用：首次注册三表，再次三表均 `skipped`、`registered` 为空；`configureResource` 每次各调 1 次。`reload()` ≡ `start()`，同样幂等。

### DDL 边界

插件**不建表**；三表 DDL 由接入方既有 `syncSchema`（node）/ `load_defs`（py）覆盖。

## 逐端契约清单

| 能力 · 端 | 签名 | 返回 / 语义 |
|---|---|---|
| `capability.schemas` · node | `schemas()` | `Array<object>`（三表**深拷贝**，调用方改写不影响内部） |
| `capability.schemas` · py | `schemas()` | `list[dict]`（同上，深拷贝） |
| `capability.create` · node | `create(store, opts)` | `{ async start(), async reload() }` |
| `capability.create` · py | `create(store, opts=None)` | `_Handle`，具 `async start()` / `async reload()`；`opts` 键与 node **同构**（camelCase：`providers`/`url`/`sign`/`schema`） |
| `adapter.download` · node | `download(store, opts = {})` → `async (req, rec, id) => {body, contentType, fileName}` | store-api `fileResolver` 契约；**camelCase 键**（对齐 `store-api/node` 既有读取） |
| `adapter.download` · py | `download(store, opts=None)` → `async (request, rec, rid) -> dict` | store-api py `file_resolver` 契约；`opts` 键同 node（`field` / `order`）；**camelCase 键**（对齐 `store-api/py` 的 `out.get("contentType")` / `out.get("fileName")`） |
| `adapter.upload` · node | `upload(store)` → `async (input) => store.resourcePut(input)` | 薄透传，不改写入参 / 出参 |
| `adapter.upload` · py | `upload(store)` → `async (input: dict) => await store.resource_put(**input)` | 薄透传，`input` 键为 py 原生（`file_name` / `mime` / `kind` / `bind` / `bytes`） |

**宿主门面同步 / 异步分流**：`register` / `has` / `configureResource`（py `configure_resource`）为**同步**；`resourcePut` / `resourceOpen` / `queryOne`（py `resource_put` / `resource_open` / `query_one`）为**异步**。

## 错误语义

| 情形 | 插件行为 |
|---|---|
| `download` 记录缺引用字段 / 引用为空 | 抛**普通 `Error`**（中文 message，**无 `ERR_` 前缀**） |
| `capability.create` 配置非法（未知顶层键 / 类型不符 / 缺门面方法） | 抛 `Error`，消息含字段名 / 方法名 |
| `resourceOpen` 未命中 / 底层读取失败 | 宿主抛错，插件**原样上抛、不捕获、不改写** |

- 插件**不产生**任何 HTTP 状态码 / 错误名（`404` / `NOT_FOUND` / `ERR_*` / `500` 等一律禁止）；
- 下载「记录不存在或 `fileField` 为空 → `404 NOT_FOUND`」属 **store-api 皮**既有行为（依据「资源数据驱动 04」§4 端点契约），插件不承担该语义。

## 依赖与宿主解耦

- **插件零宿主依赖**：不 `require('nodejs-store')`、不 `import py_store`，也不依赖任何 core / 皮肤包；`store` 实例由接入方**作为参数**传入，插件只调其既有门面；
- 宿主包在 `package.json` / `pyproject.toml` 中**仅作 optional peer 兼容性声明**（`nodejs-store >=3.0.0` / `py-store >=3.0.0`），不产生运行时依赖；
- **无任何第三方运行时依赖**（node 标准库 / py 标准库即可）；
- 插件内**不做** sha1 / 内容寻址 / URL 拼接（`createHash` / `hashlib` / `resourceComposeUrl` / `resource_compose_url`）——已下沉 core，插件零实现。

## 附录 A：三 schema 定义（唯一事实源）

> 声明：本附录为三表唯一事实源；`node/src/schemas.js` 与 `py/src/store_resource_bootstrap/schemas.py` 须逐字复制（语义深比较全等），conformance A9 校验。
> **要点**：`Resource.idPrefix` 必须为空串 `""`（falsy）——宿主仅当 `idPrefix` 真值才生成 `_id`，否则会为内容寻址资源生成随机 `_id`、破坏 `resourceId = sha1` 约定。

```json
[
  {
    "name": "Resource", "collection": "resources", "idPrefix": "", "timestamps": true,
    "read": [], "write": [],
    "fields": {
      "_id":      { "type": "string" },
      "sha1":     { "type": "string" },
      "fileName": { "type": "string" },
      "mime":     { "type": "string" },
      "size":     { "type": "int" },
      "kind":     { "type": "string" }
    },
    "relations": {},
    "indexes": [
      { "keys": { "sha1": 1 }, "options": { "unique": true } }
    ]
  },
  {
    "name": "ResourceLocation", "collection": "resource_locations", "idPrefix": "rl", "timestamps": true,
    "read": [], "write": [],
    "fields": {
      "_id":        { "type": "string" },
      "resourceId": { "type": "string" },
      "backend":    { "type": "string" },
      "key":        { "type": "string" },
      "status":     { "type": "string" },
      "priority":   { "type": "int" }
    },
    "relations": {
      "resource": { "model": "Resource", "type": "one", "localField": "resourceId", "foreignField": "_id", "read": [] }
    },
    "indexes": [
      { "keys": { "resourceId": 1, "backend": 1 }, "options": { "unique": true } }
    ]
  },
  {
    "name": "ResourceBinding", "collection": "resource_bindings", "idPrefix": "rb", "timestamps": true,
    "read": [], "write": [],
    "fields": {
      "_id":           { "type": "string" },
      "resourceId":    { "type": "string" },
      "businessTable": { "type": "string" },
      "businessId":    { "type": "string" },
      "userId":        { "type": "string" }
    },
    "relations": {
      "resource": { "model": "Resource", "type": "one", "localField": "resourceId", "foreignField": "_id", "read": [] }
    },
    "indexes": [
      { "keys": { "resourceId": 1, "businessTable": 1, "businessId": 1 }, "options": { "unique": true } }
    ]
  }
]
```

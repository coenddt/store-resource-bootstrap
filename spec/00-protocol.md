# 00 — 资源引导插件包：引导协议

> 唯一事实源：02（node）/ 03（py）两端的一切字段名、取值、签名一律回指本文件，不得另立口径。
> 日期：2026-10-05
> 上游依据：`doc/execution/2026/10/已完成-资源数据驱动-02/03/04-*.md`（宿主资源能力 / 三 schema / 皮下载端点）。

## 定位

`store-resource-bootstrap` 属于 common-store「插件 / 胶水」层（**非协议皮、非宿主、非 core**），形态复刻 `store-rbac-bootstrap`（读配置 → 挂接既有接缝），只做两件事：

1. **能力引导**：把接入方**注入**的 schema 定义（`schemas`，可选；缺省不注册任何表）注册进宿主 store（`register`，幂等），并把 `providers` / `url` / `sign` / `schema` / `fields` 装配给宿主既有资源门面 `configureResource`；
2. **接缝适配**：产出皮肤**读写**所需的 `fileResolver`（`download`）与 `uploadResolver`（上传），另保留薄透传的 `resourcePut`（`upload`）。

显式声明**双命名空间**：

- `capability`：能力引导（`schemas` / `create`）；
- `adapter`：接缝适配（`download` / `upload` / `uploadResolver`）。

另随包提供**可选参考 provider 命名空间** `providers`（`oss` / `minio`，S3 兼容预设；SDK 懒加载），供接入方在 `providerPlugins` 中直接引用。

**schema 归属**：库**不内置权威资源 schema**。

- **业务实体 schema**（如 `product.images` / `user.avatar` 引用的业务表）**一概不涉及**——数据的理解与结构由业务上层定义，库零定义、零占位；
- **资源仓储自身的元数据 schema**（`Resource` / `ResourceLocation` / `ResourceBinding`，属资源能力自身的持久化模型）**仅作可选参考定义**随包提供（`capability.schemas()`）；是否注册、注册哪套，由接入方经 `opts.schemas` 注入决定（缺省 `[]` → **不注册任何表**，DDL 与资源模型全交业务/宿主）；
- **资源三表的字段结构同样任业务自定义**：三表的列名**不写死在宿主**，而是由接入方经 `opts.fields` 的「逻辑角色 → 物理字段名」映射声明（缺省 = canonical 列名）。库只封装上传 / 下载 / 存储这些**通用代码**，字段命名与结构交业务上层定义，避免把业务数据模型耦合进通用库。

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
  "providerPlugins": [ { "kind": "oss", "create": "<provider 工厂函数 create(options)>" } ],  // 可选；缺省 []
  "schemas": [ "<schema 定义，见附录 A / capability.schemas()>" ],  // 可选；缺省 []（不注册任何表）
  "url":  { "base": "https://cdn.example.com" },  // 可选；→ configureResource({url})。缺省 {}
  "sign": null,                                    // 可选；函数或 null。缺省 null → configureResource({sign})
  "schema": { "resource": "Resource", "location": "ResourceLocation", "binding": "ResourceBinding" },  // 可选；缺省宿主同名
  "fields": {                                       // 可选；逻辑角色 → 物理字段名映射。缺省 = canonical
    "resource": { "sha1": "sha1", "fileName": "fileName", "mime": "mime", "size": "size", "kind": "kind" },
    "location": { "resourceId": "resourceId", "backend": "backend", "key": "key", "status": "status", "priority": "priority" },
    "binding": { "resourceId": "resourceId", "businessTable": "businessTable", "businessId": "businessId", "userId": "userId" }
  }
}
```

| 字段 | 允许类型 / 取值 | 缺省 | 备注 |
|---|---|---|---|
| `providers` | **必填**，非空数组；每项 `{kind: 非空字符串, options?: 对象, priority?: 整数}` | 无（必填） | `kind` 须为宿主**已注册**的 provider（`local` / `s3` 内置；其余由接入方经宿主自备）。插件**不预检** kind 有效性，交宿主抛错 |
| `providerPlugins` | 数组；每项 `{kind: 非空字符串, create: 函数}` | `[]` | provider 工厂注册表；`create(options) -> provider`。**非空时**要求宿主具 `registerProvider`（py `register_provider`）。插件**不预检** kind 冲突，交宿主注册表处置 |
| `schemas` | 数组 \| `null` \| `false` | `[]` | **注册进宿主的 schema 定义注入点**（库不内置权威 schema）。数组逐项须为对象且 `name` 非空字符串，按序 `register`（幂等）；`null` / `false` / 缺省 → **不注册任何表**（DDL 与资源模型全交业务/宿主）。业务实体 schema 不在此列——由业务自管，库不涉 |
| `url` | 对象 | `{}` | 原样传 `configureResource` |
| `sign` | 函数 \| `null` | `null` | 原样传 `configureResource` |
| `schema` | 对象 | `{resource:'Resource',location:'ResourceLocation',binding:'ResourceBinding'}` | 三 schema 名映射；原样传 `configureResource` |
| `fields` | 对象 | canonical（见上） | 三表**逻辑角色 → 物理字段名**映射；原样传 `configureResource({fields})`，使资源三表字段结构由业务自定义。校验：未知表 / 未知角色 → 抛 `Error`；**必填角色**（`resource.sha1`、`location.resourceId`/`backend`/`key`、`binding.resourceId`/`businessTable`/`businessId`）须为非空字符串；**可选角色**为非空字符串或 `null`（`null` = 跳过该列不落库）。`_id` 不可映射（core 身份，去重按 `_id`）。**仅在提供该键时**才透传（缺省不传 → 宿主用 canonical，逐字节兼容） |

- 顶层**仅允许** `providers` / `providerPlugins` / `schemas` / `url` / `sign` / `schema` / `fields` 七个键；出现未知键 → 抛 `Error`（禁静默忽略，对齐 no-error-masking）。

`adapter.download(store, opts)` 的 `opts`：

| 字段 | 允许类型 / 取值 | 缺省 | 备注 |
|---|---|---|---|
| `field` | 非空字符串 | `'file'` | 记录上承载资源引用的字段名；支持点路径（如 `images.original`）；请求级 `?field` 优先于本项 |
| `order` | 数组 \| `undefined` | `undefined` | 引用为数组时的取值顺序提示；缺省按原序 |

`adapter.uploadResolver(store, opts)` 的 `opts`：

| 字段 | 允许类型 / 取值 | 缺省 | 备注 |
|---|---|---|---|
| `kind` | 非空字符串 | `'file'` | 写入 `Resource.kind` 的资源类别 |
| `bind` | 函数 \| `null` | `null` | `(req, rec, id) => {businessTable, businessId} \| null`；返回 null 则不写 `ResourceBinding` |

## 引导规则

### 入口

```js
const { capability, adapter } = require('store-resource-bootstrap-node');
```

```python
from store_resource_bootstrap import capability, adapter
```

### `start()` 固定序列（node；py 同构，门面名 snake_case）

1. 注册 `providerPlugins`（**同步**）：node `store.registerProvider(spec.kind, { create: spec.create })`；py `store.register_provider(spec.kind, SimpleNamespace(create=spec.create))`；**先于** `configureResource`；
2. 按 `opts.schemas` 生效集逐表幂等注册（`has` / `register` **同步**调用，无 `await`；缺省 `[]` → 本步空转）：
   `for (const defn of schemas) { store.has(defn.name) ? skipped.push(defn.name) : (store.register(defn), registered.push(defn.name)) }`
3. `await store.configureResource({ providers, url, sign, schema })`（**异步**；py 用 sync / async 兼容包装）；
4. 返回 `{ registered: string[], skipped: string[], providerRegistered: string[] }`（可观测，禁静默）。

### `reload()` 固定序列

≡ 再跑一次 `start()`（宿主 `configure` 为整体替换 `_pool`，无需先清除）。

### 构造期校验

`capability.create` 内，任一不符抛 `Error`（消息含字段名）：

1. `store` 具 `register` / `has` / `configureResource`（py `configure_resource`）；
2. `providers` 为非空数组，逐项按「配置形状」校验（`kind` 非空字符串、`options` 对象、`priority` 整数）；
3. `url` 为对象；
4. `sign` 为函数或 `null`；
5. `schema` 为对象；
6. `providerPlugins` 缺省 `[]`；若给定须为数组，逐项 `kind` 非空字符串、`create` 函数；**当且仅当非空**时 `store` 须具 `registerProvider`（py `register_provider`）；
7. `schemas` 缺省 `[]`；若给定须为数组（逐项为对象且 `name` 非空字符串）或 `null` / `false`；否则抛 `Error`（消息含 `schemas`）；
8. `fields` 缺省 `undefined`（→ 不传宿主，走 canonical）；若给定须为对象，且三表**仅含已知逻辑角色**、未知表 / 未知角色 / 必填角色非非空字符串 / 可选角色非（非空字符串 | `null`）→ 抛 `Error`（消息含表 / 角色名）。校验在构造期完成，**零写库**。

### 幂等

`start()` 可重复调用：首次注册 `opts.schemas` 生效集，再次均 `skipped`、`registered` 为空（缺省 `[]` 时两次均空）；`configureResource` 每次各调 1 次。`reload()` ≡ `start()`，同样幂等。

### DDL 边界

插件**不建表**；是否建表、建哪些表由接入方决定（业务既有 `syncSchema`（node）/ `load_defs`（py））。`opts.schemas` 只把定义 `register` 进宿主的 schema 注册表（供 `configureResource` 的 `schema` 名映射引用），**不触发 DDL**。

## 逐端契约清单

| 能力 · 端 | 签名 | 返回 / 语义 |
|---|---|---|
| `capability.schemas` · node | `schemas()` | `Array<object>`：内置**可选参考**定义（三表**深拷贝**，调用方改写不影响内部；库不据此强制注册） |
| `capability.schemas` · py | `schemas()` | `list[dict]`（同上，深拷贝） |
| `capability.create` · node | `create(store, opts)` | `{ async start(), async reload() }` |
| `capability.create` · py | `create(store, opts=None)` | `_Handle`，具 `async start()` / `async reload()`；`opts` 键与 node **同构**（camelCase：`providers`/`providerPlugins`/`schemas`/`url`/`sign`/`schema`/`fields`） |
| `adapter.download` · node | `download(store, opts = {})` → `async (req, rec, id) => {body, contentType, fileName}` | store-api `fileResolver` 契约；**camelCase 键**（对齐 `store-api/node` 既有读取） |
| `adapter.download` · py | `download(store, opts=None)` → `async (request, rec, rid) -> dict` | store-api py `file_resolver` 契约；`opts` 键同 node（`field` / `order`）；**camelCase 键**（对齐 `store-api/py` 的 `out.get("contentType")` / `out.get("fileName")`） |
| `adapter.upload` · node | `upload(store)` → `async (input) => store.resourcePut(input)` | 薄透传，不改写入参 / 出参 |
| `adapter.upload` · py | `upload(store)` → `async (input: dict) => await store.resource_put(**input)` | 薄透传，`input` 键为 py 原生（`file_name` / `mime` / `kind` / `bind` / `bytes`） |
| `adapter.uploadResolver` · node | `uploadResolver(store, opts = {})` → `async (req, rec, id) => { ref }` | store-api `uploadResolver` 契约；`req.body` 为皮已缓冲的 `Buffer` |
| `adapter.uploadResolver` · py | `upload_resolver(store, opts=None)` → `async (request, rec, rid) -> dict` | store-api py `upload_resolver` 契约；`request` 兼容 Starlette Request / dict；`opts` 键同 node（`kind` / `bind`） |

**宿主门面同步 / 异步分流**：`register` / `has` / `configureResource`（py `configure_resource`）/ `registerProvider`（py `register_provider`）为**同步**；`resourcePut` / `resourceOpen`（py `resource_put` / `resource_open`）为**异步**。插件只经 `resourceOpen` 取字节与元数据，**不再依赖 `queryOne` / `query_one`**——`resourceOpen` 成功时已附带返回 `fileName` / `mime`（元数据缺失 → `null`，宿主发 `resourceMetaMissing` 反馈，仍出字节），`download` 据此兜底。

## 错误语义

| 情形 | 插件行为 |
|---|---|
| `download` 记录缺引用字段 / 引用为空 | 抛**普通 `Error`**（中文 message，**无 `ERR_` 前缀**） |
| `uploadResolver` 请求体为空 / `resourcePut` 未返回 `resourceId` | 抛**普通 `Error`**（中文 message，**无 `ERR_` 前缀**） |
| `capability.create` 配置非法（未知顶层键 / 类型不符 / 缺门面方法 / `fields` 未知表或角色、必填角色非非空字符串） | 抛 `Error`，消息含字段名 / 方法名 / 表名 / 角色名 |
| `resourceOpen` 未命中 / 底层读取失败 | 宿主抛错，插件**原样上抛、不捕获、不改写** |

- 插件**不产生**任何 HTTP 状态码 / 错误名（`404` / `NOT_FOUND` / `ERR_*` / `500` 等一律禁止）；
- 下载「记录不存在或 `fileField` 为空 → `404 NOT_FOUND`」属 **store-api 皮**既有行为（依据「资源数据驱动 04」§4 端点契约），插件不承担该语义。

## 依赖与宿主解耦

- **插件零宿主依赖**：不 `require('nodejs-store')`、不 `import py_store`，也不依赖任何 core / 皮肤包；`store` 实例由接入方**作为参数**传入，插件只调其既有门面；
- 宿主包在 `package.json` / `pyproject.toml` 中**仅作 optional peer 兼容性声明**（`nodejs-store >=4.3.0` / `py-store >=4.3.0`；`4.3.0` 起宿主支持 `configureResource({fields})` 字段映射与 `resourceOpen` 附带 `fileName` / `mime`），不产生运行时依赖；
- **默认无任何第三方运行时依赖**（node 标准库 / py 标准库即可）；**可选参考 provider 模块**（`providers.oss` / `providers.minio`）需要 S3 兼容 SDK（node `@aws-sdk/client-s3`、py `boto3`）——声明为**可选依赖**、**懒加载**：未安装时模块可装载、`capability` / `adapter` 与测试均不受影响，仅实际调用该模块 `create()` 时报错。
- 插件内**不做** sha1 / 内容寻址 / URL 拼接（`createHash` / `hashlib` / `resourceComposeUrl` / `resource_compose_url`）——已下沉 core，插件零实现。

## 附录 A：三 schema 参考定义（可选参考，非权威）

> 声明：本附录为**可选参考**默认定义（开箱即用）；库**不据此强制注册**。`node/src/schemas.js` 与 `py/src/store_resource_bootstrap/schemas.py` 须与本附录逐字一致（语义深比较全等），conformance 校验。是否注册由接入方经 `opts.schemas` 决定（缺省不注册）；**业务实体 schema 由业务自管，不在本附录（库不涉）**。
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

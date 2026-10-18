# store-resource-bootstrap

common-store 数据层家族的**可选资源引导插件**。它装配宿主的资源能力（`providers` / `url` / `sign` / `schema` / `fields`），并产出 store-api 文件接缝所需的 `download` / `upload` / `uploadResolver`，用于文件**下载**与**上传**。

> English: [README.md](./README.md)
> 唯一事实源：[`spec/00-protocol.md`](./spec/00-protocol.md)

## 2. 运行时 / 包矩阵

| 运行时 | 包名 | 版本 | 导入 | 宿主包（可选 peer） | 引擎下限 |
|---|---|---|---|---|---|
| Node | `store-resource-bootstrap-node` | `0.3.1` | `require('store-resource-bootstrap-node')` | `nodejs-store >= 4.3.0` | `node >= 18` |
| Python | `store-resource-bootstrap-py` | `0.3.1` | `from store_resource_bootstrap import capability, adapter` | `py-store >= 4.3.0` | `python >= 3.10` |

每个运行时的对外表面均由三个命名空间组成：

| 命名空间 | 成员 | 用途 |
|---|---|---|
| `capability` | `schemas()`、`create(store, opts)` | 注册接入方注入的 schema + 装配宿主资源池 |
| `adapter` | `download(store, opts)`、`upload(store)`、`uploadResolver(store, opts)` | 产出 store-api 文件接缝所需的 resolver |
| `providers` | `oss`、`minio` | 可选参考 S3 兼容 provider 工厂 |

可选的第三方 SDK（声明为可选、**懒加载**——未安装时包仍可导入，`capability` / `adapter` 命名空间可正常工作；仅实际调用某 provider 的 `create()` 时才需要 SDK）：

| 运行时 | SDK | 声明方式 |
|---|---|---|
| Node | `@aws-sdk/client-s3 ^3.1146.0` | `optionalDependencies` |
| Python | `boto3 >= 1.34` | 可选 extra `providers`（`pip install "store-resource-bootstrap-py[providers]"`） |

宿主包（`nodejs-store` / `py-store`）**仅声明为可选 peer 依赖**——本插件从不 import / require 它们；store 实例始终由接入方传入。

## 3. 目录

1. [标题 + 定位](#store-resource-bootstrap)
2. [运行时 / 包矩阵](#2-运行时--包矩阵)
3. [目录](#3-目录)
4. [它是什么](#4-它是什么)
5. [何时用 / 何时不用](#5-何时用--何时不用)
6. [安装](#6-安装)
7. [快速上手](#7-快速上手)
8. [能力引导（`capability.*`）](#8-能力引导)
9. [Adapter 参考（`download` / `upload` / `uploadResolver`）](#9-adapter-参考)
10. [Providers（`oss` / `minio` / `s3-compat`）](#10-providers)
11. [配置参考（七键）](#11-配置参考)
12. [`fields` 映射（逻辑角色 → 物理字段）](#12-fields-映射)
13. [DDL 边界](#13-ddl-边界)
14. [错误映射](#14-错误映射)
15. [场景事例](#15-场景事例)
16. [定制化 / 扩展点](#16-定制化--扩展点)
17. [边界与非目标](#17-边界与非目标)
18. [FAQ](#18-faq)
19. [开发](#19-开发)
20. [相关项目](#20-相关项目)
21. [License](#21-license)

## 4. 它是什么

`store-resource-bootstrap` 位于 common-store 的**插件 / 胶水层**（它*不是*协议皮、*不是*宿主、*不是* core）。其形态复刻 `store-rbac-bootstrap`：读配置 → 挂接既有接缝。它只做两件事：

1. **能力引导** —— 把接入方**注入**的 schema 定义（`schemas`，可选；缺省不注册任何表）注册进宿主 store，然后调用宿主既有的资源门面 `configureResource({ providers, url, sign, schema, fields })`。
2. **接缝适配** —— 产出皮肤所需的 `fileResolver`（`download`）与 `uploadResolver`（上传），另加一个薄透传的 `resourcePut`（`upload`）。

它对外暴露两个显式命名空间——`capability`（引导：`schemas` / `create`）与 `adapter`（接缝：`download` / `upload` / `uploadResolver`）——并随包提供一个**可选参考 provider 命名空间** `providers`（`oss` / `minio`，S3 兼容预设），接入方可直接在 `providerPlugins` 中引用。

**它在架构中的位置。** 宿主（`nodejs-store` / `py-store`）持有资源能力本身：schema 注册表、由 `providers` 构建的资源池，以及自 `4.3.0` 起新增的 `configureResource({ fields })` 字段映射与同时返回 `fileName` / `mime` 的 `resourceOpen` 读取。皮肤（`store-api`）持有 HTTP 暴露：`GET` / `POST /{resource}/:id/file` 子路由经注入的 `fileResolver` 取字节、经注入的 `uploadResolver` 存字节。本插件两者都不持有：它正是那块**装配能力**并**产出 resolver** 的部件，让业务只写胶水，永不重写 HTTP 路由或 DDL。

**schema 归属。** 库**不内置任何权威资源 schema**。

- **业务实体 schema**（如 `product.images` / `user.avatar` 背后的表）永不被触碰——由业务层定义并持有；本库对它们零定义、零占位。
- **资源能力自身的元数据 schema**（`Resource` / `ResourceLocation` / `ResourceBinding`）仅经 `capability.schemas()` **作为可选参考**提供。是否注册由接入方经 `opts.schemas` 决定（缺省 `[]` → **不注册任何表**，因而 DDL 与资源模型完全由业务 / 宿主决定）。
- **资源三表的列结构同样由业务可定义**：其列名不写死在宿主；接入方经 `opts.fields` 的「逻辑角色 → 物理字段名」映射声明（缺省 = canonical 列名）。

三条铁律：

- **零语义发明** —— 插件不产出任何 HTTP 状态码、任何错误名、任何错误前缀；它只抛普通 `Error`（Node）/ `ValueError`（Python）。下载的 `404` 语义位于既有 store-api 皮肤。
- **零宿主依赖** —— 它从不 `require('nodejs-store')` / `from py_store import ...`，也从不依赖任何 core 或皮肤包；store 实例以参数传入。
- **零回归** —— 它不修改任何兄弟仓库；纯增量。

## 5. 何时用 / 何时不用

**在以下情形使用**——你正在把 common-store 资源能力集成进某服务，并希望：

- 一次调用即可在宿主 store 上注册资源 schema 并装配资源池；
- 拿到现成的 `fileResolver` / `uploadResolver` 交给 `store-api`，让字节经既有 `/{resource}/:id/file` 子路由流动，无需新增 HTTP 路由；
- 资源表列名可配置（`fields`），无需改业务代码；
- 有一个 S3 兼容的 `oss` / `minio` provider 工厂可用，无需自己写存储适配器。

**在以下情形不要使用**——若你期望它：

- 建表或执行 DDL（它从不做——见 §13）；
- 暴露 HTTP 路由或产出状态码 / 错误名（那是 `store-api` 的职责）；
- 持有或定义你的业务实体 schema（由业务持有）；
- 生成预签名 URL 或绕过数据层直传存储（**不提供**——上传始终经宿主 `resourcePut`；见 §16 / §17）。

## 6. 安装

### Node

```bash
npm i store-resource-bootstrap-node
# 仅当使用可选的 oss / minio provider 时：
npm i @aws-sdk/client-s3
```

### Python

```bash
pip install store-resource-bootstrap-py
# 仅当使用可选的 oss / minio provider 时：
pip install "store-resource-bootstrap-py[providers]"
```

本插件**默认无任何第三方运行时依赖**（Node / Python 标准库足够）。可选的 `oss` / `minio` 模块需要 S3 兼容 SDK（`@aws-sdk/client-s3` / `boto3`），其为**懒加载**：未安装时模块仍可装载，`capability` / `adapter` 与测试均不受影响——仅实际调用该模块的 `create()` 时报错。

## 7. 快速上手

### Node（`store-resource-bootstrap-node`）

```js
const { store } = require('nodejs-store');                 // 宿主 store（由接入方传入）
const { capability, adapter } = require('store-resource-bootstrap-node');

// 能力引导：按需注入 schema 定义并装配资源池。
// `schemas` 缺省为 [] → 不注册任何表；可传 capability.schemas() 用内置
// 可选参考集，或传自有定义。
const handle = capability.create(store, {
  providers: [{ kind: 'local', options: { root: '/data/resources' }, priority: 0 }],
  schemas: capability.schemas(),
});
const out = await handle.start();
// out === { registered: ['Resource', 'ResourceLocation', 'ResourceBinding'], skipped: [], providerRegistered: [] }
// await handle.reload();  // 再跑一次 start()

// 接缝适配：store-api fileResolver（GET  /{resource}/:id/file）
const fileResolver = adapter.download(store);
// 接缝适配：store-api uploadResolver（POST /{resource}/:id/file）
const uploadResolver = adapter.uploadResolver(store);
// store.resourcePut(input) 的薄透传
// const put = adapter.upload(store);
```

### Python（`store-resource-bootstrap-py`）

```python
import asyncio
from py_store import store                                 # 宿主 store（由接入方传入）
from store_resource_bootstrap import capability, adapter

async def main():
    handle = capability.create(store, {
        "providers": [{"kind": "local", "options": {"root": "/data/resources"}, "priority": 0}],
        "schemas": capability.schemas(),   # 缺省 [] → 不注册任何表
    })
    out = await handle.start()
    # out == {"registered": ["Resource", "ResourceLocation", "ResourceBinding"], "skipped": [], "providerRegistered": []}
    # await handle.reload()

    file_resolver = adapter.download(store)
    upload_resolver = adapter.upload_resolver(store)
    # put = adapter.upload(store)   # store.resource_put(**input) 的薄透传

asyncio.run(main())
```

## 8. 能力引导

### 8.1 `capability.schemas()`

| 运行时 | 签名 | 返回 |
|---|---|---|
| Node | `schemas()` | `Array<object>` |
| Python | `schemas()` | `list[dict]` |

返回三张资源表的**内置可选参考**定义，为一**深拷贝**（改写返回值永不影响内部副本）。三个定义按序为：

| 名称 | `collection` | `idPrefix` | `fields` | 唯一索引 |
|---|---|---|---|---|
| `Resource` | `resources` | `""`（空字符串） | `_id`, `sha1`, `fileName`, `mime`, `size`, `kind` | `{ sha1: 1 }` |
| `ResourceLocation` | `resource_locations` | `rl` | `_id`, `resourceId`, `backend`, `key`, `status`, `priority` | `{ resourceId: 1, backend: 1 }` |
| `ResourceBinding` | `resource_bindings` | `rb` | `_id`, `resourceId`, `businessTable`, `businessId`, `userId` | `{ resourceId: 1, businessTable: 1, businessId: 1 }` |

本库**不**强制注册这些定义。注意 `Resource.idPrefix` 必须为空字符串——宿主仅在 `idPrefix` 为真值时才生成 `_id`，非空值会破坏 `resourceId = sha1` 约定。

### 8.2 `capability.create(store, opts)`

| 运行时 | 签名 | 返回 |
|---|---|---|
| Node | `create(store, opts)` | `{ async start(), async reload() }` |
| Python | `create(store, opts=None)` | 一个 `_Handle`，具 `async start()` / `async reload()` |

`opts` 键**跨运行时完全一致（camelCase）**——见 §11。

**构造期校验。** 任何违规都会在调用 `create()` 时立即抛错——消息含违规的字段 / 方法 / 表 / 角色名，且**零门面调用**发生（「快速失败，不做半接线」）：

1. `store` 必须暴露 `register` / `has` / `configureResource`（Python：`configure_resource`）。
2. `providers` 必须为非空数组；每项 `{ kind: 非空字符串, options?: 对象, priority?: 整数 }`。
3. `url` 必须为对象。
4. `sign` 必须为函数或 `null`。
5. `schema` 必须为对象。
6. `providerPlugins` 缺省 `[]`；若给出，必须为数组，其项具非空 `kind` 与函数 `create`。**仅当其为非空时**，`store` 必须暴露 `registerProvider`（Python `register_provider`）。
7. `schemas` 缺省 `[]`；若给出，必须为数组（每项为含非空 `name` 的对象）或 `null` / `false`；出现未知顶层键同样抛错。
8. `fields` 缺省 `undefined`（→ 不透传，宿主用 canonical）；若给出，必须为对象，且仅含已知表 / 角色与类型正确的值（见 §12）。

### 8.3 `start()` 固定序列

`start()` 运行一段固定序列（Node；Python 同构，门面名 snake_case）：

1. **注册 `providerPlugins`** —— 同步，且**先于** `configureResource`：
   `store.registerProvider(spec.kind, { create: spec.create })`（Python：`store.register_provider(spec.kind, SimpleNamespace(create=spec.create))`）。
2. **幂等注册生效的 `opts.schemas`** —— `has` / `register` 为**同步**（`has(defn.name)` → 推入 `skipped`，否则 `register(defn)` → 推入 `registered`）。缺省 `[]` 时本步空转。
3. **`await store.configureResource({ providers, url, sign, schema })`** —— 异步（Python 用兼容同步 / 异步的包装）。`fields` 键**仅在提供 `opts.fields` 时**才带；否则载荷省略它，使该调用与更早的宿主逐字节兼容。
4. **返回** `{ registered: string[], skipped: string[], providerRegistered: string[] }` —— 可观测，禁静默。

返回示例：

```js
// 首次，带 schemas: capability.schemas()
{ registered: ['Resource', 'ResourceLocation', 'ResourceBinding'], skipped: [], providerRegistered: [] }
// 第二次 start()（幂等）
{ registered: [], skipped: ['Resource', 'ResourceLocation', 'ResourceBinding'], providerRegistered: [] }
// 缺省（未注入 schemas）
{ registered: [], skipped: [], providerRegistered: [] }
```

### 8.4 幂等与 `reload()`

`start()` 可重复调用。首次调用注册生效的 `opts.schemas`；此后每次调用都在 `skipped` 中报告它们，`registered` 为空（`configureResource` 每次 `start()` 仍会被调用一次）。`reload()` 就是再跑一次 `start()`——宿主的 `configure` 整体替换资源池，故无需清理。

## 9. Adapter 参考

### 9.1 `adapter.download(store, opts)`

| 运行时 | 签名 | 返回 |
|---|---|---|
| Node | `download(store, opts = {})` | `async (req, rec, id) => { body, contentType, fileName }` |
| Python | `download(store, opts=None)` | `async (request, rec, rid) -> dict` |

产出 store-api **`fileResolver`** 契约，用于 `GET /{resource}/:id/file`。

**构造期校验**（立即抛错）：`store` 必须暴露 `resourceOpen`（Python `resource_open`）；`opts` 必须为对象；`field` 若给出必须为非空字符串。注意**无** `queryOne` 的宿主也没问题——resolver 只经 `resourceOpen` 读取。

`opts`：

| 键 | 类型 / 取值 | 缺省 | 备注 |
|---|---|---|---|
| `field` | 非空字符串 | `'file'` | 记录上承载资源引用的字段名。支持**点路径**（如 `images.original`）。请求级 `?field` 将其覆盖。 |
| `order` | 数组 \| `undefined` | `undefined` | 当引用为数组时，提示后端尝试顺序；缺省为自然顺序。透传给 `resourceOpen(ref, { order })`。 |

**调用时行为** `(req, rec, id)`：

1. 解析字段路径：请求级 `req.query.field`（非空字符串）优先于构造期 `field`。
2. 按该路径从记录读取引用。缺失 / 空字符串 / `null` 引用抛普通 `Error`，消息含该字段路径——**零资源调用**发生。
3. `await store.resourceOpen(ref, order === undefined ? {} : { order })`。
4. 返回 `{ body: opened.bytes, contentType: opened.mime || 'application/octet-stream', fileName: opened.fileName || String(ref) }`。

元数据（`mime` / `fileName`）随 `resourceOpen` 结果一并返回——插件**不再调用 `queryOne`**（这正是无 `queryOne` 的宿主仍可用的原因）。当 `mime` 为 `null` / 空时，`contentType` 兜底为 `application/octet-stream`；当 `fileName` 为 `null` / 空时，`fileName` 兜底为引用字符串。

底层读取失败：宿主抛错，插件**原样传播**——从不捕获或改写。

### 9.2 `adapter.upload(store)`

| 运行时 | 签名 | 返回 |
|---|---|---|
| Node | `upload(store)` | `async (input) => store.resourcePut(input)` |
| Python | `upload(store)` | `async (input: dict) => await store.resource_put(**input)` |

**薄透传**：不触碰写入入参 / 出参；其形状恰为宿主 `resourcePut` / `resource_put` 所期望。Node 入参键为 Node 原生（camelCase——如 `bytes`、`fileName`、`mime`、`kind`、`bind`）；Python 入参键为 Python 原生（snake_case——如 `bytes`、`file_name`、`mime`、`kind`、`bind`）。若 `store` 缺 `resourcePut` / `resource_put`，构造时抛错。

### 9.3 `adapter.uploadResolver(store, opts)`

| 运行时 | 签名 | 返回 |
|---|---|---|
| Node | `uploadResolver(store, opts = {})` | `async (req, rec, id) => { ref }` |
| Python | `upload_resolver(store, opts=None)` | `async (request, rec, rid) -> dict` |

产出 store-api **`uploadResolver`** 契约（与 `download` 对称），用于 `POST /{resource}/:id/file`。Node 下 `req.body` 为**皮已缓冲的 `Buffer`**。

**构造期校验**（立即抛错）：`store` 必须暴露 `resourcePut` / `resource_put`；`opts` 必须为对象；`kind` 若给出必须为非空字符串；`bind` 若给出必须为函数。

`opts`：

| 键 | 类型 / 取值 | 缺省 | 备注 |
|---|---|---|---|
| `kind` | 非空字符串 | `'file'` | 写入 `Resource.kind` 的资源类别。 |
| `bind` | 函数 \| `null` | `null` | `(req, rec, id) => { businessTable, businessId } \| null`；返回 `null` 则不写 `ResourceBinding`。 |

**调用时行为** `(req, rec, id)`：

1. 取字节体：Node 若 `req.body` 为 `Buffer` 则用之；Python 对 Starlette 请求 `await request.body()`，对 dict `request["body"]`。空体抛普通 `Error`（消息含「上传字节体」）——**零 `resourcePut` 调用**发生。
2. 构建 `resourcePut` 入参：`{ bytes, kind }`，外加：
   - `fileName`（Node）/ `file_name`（Python）——`req.query.fileName` 非空则用，否则 `rec.fileName` 非空则用，否则省略；
   - `mime`——`req.query.mime` 非空则用，否则 `content-type` 头非空则用，否则省略；
   - `bind`——仅当 `bind` 为函数且返回非 null 时。
3. `await store.resourcePut(input)`（Python `store.resource_put(**input)`）。插件**自身不做任何 IO**——字节写入由数据层完成。
4. 返回 `{ ref }`，其中 `ref = out.resourceId`。若 `resourcePut` 未返回 `resourceId`，抛普通 `Error`。

## 10. Providers

可选参考 `providers` 命名空间暴露两个 S3 兼容工厂——`oss` 与 `minio`——二者均构建于同一共享基模块 `s3-compat` 之上。（公开命名空间仅导出 `oss` 与 `minio`；`s3-compat` 是共享基，仅能深导入，其缺省 `kind` 为 `'s3'`。）

| Provider | Node 模块 | Python 模块 | `kind` | `forcePathStyle` | signatureVersion | 寻址理由 |
|---|---|---|---|---|---|---|
| `oss` | `src/providers/oss.js` | `providers/oss.py` | `'oss'` | `false`（virtual-hosted） | 仅 Python：`'s3'`（V2） | OSS 仅支持 virtual-hosted（bucket 在域名中）。Node 默认 SigV4（无需额外配置）；boto3 必须用 V2 签名。 |
| `minio` | `src/providers/minio.js` | `providers/minio.py` | `'minio'` | `true`（path-style） | — | 自托管网关需 path-style（bucket 在路径中）。 |
| `s3-compat`（基） | `src/providers/s3-compat.js` | `providers/s3_compat.py` | `'s3'`（缺省） | `?? !!endpoint`（Node）/ 缺省为 `bool(endpoint)`（Python） | — | 通用 S3 兼容基；也可用于 AWS。命名空间索引不重新导出它。 |

**Node `oss.create(options, deps)` / `minio.create(options, deps)`** 将各自预设与 `options` 合并后委托给 `s3-compat.create`。基 `create(options, deps)`：

- 若注入 `deps` 则用之，否则懒 `require('@aws-sdk/client-s3')`；
- 要求 `options.bucket`（抛 `s3-compat provider 需要 options.bucket`）；
- 用 `options.client` 构建客户端，或新建 `S3Client`，配置 `{ region: options.region || 'us-east-1', endpoint: options.endpoint, forcePathStyle: options.forcePathStyle ?? !!options.endpoint, credentials: options.credentials }`；
- 对所有 key 施加 `options.prefix`（`prefix/<key>`）；
- 返回 `{ kind, put, get, remove, exists }`。

**Python `oss.create(options, sdk)` / `minio.create(options, sdk)`** 合并预设后委托给 `s3_compat.create`。基 `create(options, sdk=None)`：

- 未注入 `sdk` 时懒 `import boto3` / `from botocore.config import Config`；
- 要求 `options.bucket`；
- 用 `options.client` 构建客户端，否则 `sdk["client"]("s3", region_name=..., endpoint_url=..., aws_access_key_id=..., aws_secret_access_key=..., config=...)`，其中 path-style 时 `addressing_style` 为 `"path"` 否则为 `"virtual"`，并在设置 `signatureVersion` 时加 `signature_version`；
- 施加 `options.prefix`；
- 返回 `{ kind, put, get, remove, exists }`，四者**均为 async**（经 `asyncio.to_thread` 派发）。

**Provider 选项（除注明外，双端通用）：**

| 选项 | 含义 |
|---|---|
| `bucket` | **必填。** 目标 bucket。 |
| `region` | 区域；缺省 `us-east-1`。 |
| `endpoint` | S3 兼容端点 URL。 |
| `forcePathStyle` | `true` → path-style，`false` → virtual-hosted。由预设提供；省略时基缺省为「当且仅当设置了 `endpoint` 时 path-style」。 |
| `credentials` | `{ accessKeyId, secretAccessKey }`。 |
| `prefix` | 可选 key 前缀（`prefix/<key>`）。 |
| `client` | 预构建的客户端实例（跳过客户端构建）。 |
| `signatureVersion` | 仅 Python。`'s3'` = V2 签名（OSS 预设使用）。 |
| `kind` | 覆盖返回的 provider `kind`（预设总是强制自己的）。 |

使用方式：经 `providerPlugins` 注册工厂，并在 `providers` 中引用该 kind：

```js
const { capability, providers } = require('store-resource-bootstrap-node');

const handle = capability.create(store, {
  providers: [{ kind: 'oss', options: { bucket: 'reports', endpoint: 'https://oss-cn-hangzhou.aliyuncs.com' }, priority: 0 }],
  providerPlugins: [{ kind: 'oss', create: providers.oss.create }],
});
await handle.start();
```

## 11. 配置参考

`capability.create(store, opts)` 接受一个 JSONC 形状的 `opts`，其键**跨运行时完全一致（camelCase）**：

```jsonc
{
  "providers": [ { "kind": "local", "options": { "root": "/data/resources" }, "priority": 0 } ],
  "providerPlugins": [ { "kind": "oss", "create": "<provider 工厂 create(options)>" } ],  // 可选；缺省 []
  "schemas": [ "<schema 定义，见 spec 附录 A / capability.schemas()>" ],  // 可选；缺省 []（不注册任何表）
  "url":  { "base": "https://cdn.example.com" },  // 可选；→ configureResource({ url })。缺省 {}
  "sign": null,                                    // 可选；函数或 null。缺省 null → configureResource({ sign })
  "schema": { "resource": "Resource", "location": "ResourceLocation", "binding": "ResourceBinding" },  // 可选；缺省宿主同名
  "fields": {                                       // 可选；逻辑角色 → 物理字段映射。缺省 = canonical
    "resource": { "sha1": "sha1", "fileName": "fileName", "mime": "mime", "size": "size", "kind": "kind" },
    "location": { "resourceId": "resourceId", "backend": "backend", "key": "key", "status": "status", "priority": "priority" },
    "binding": { "resourceId": "resourceId", "businessTable": "businessTable", "businessId": "businessId", "userId": "userId" }
  }
}
```

**顶层恰好只允许这七个键**——`providers`、`providerPlugins`、`schemas`、`url`、`sign`、`schema`、`fields`。任何未知键抛 `Error`（绝不静默忽略）。

| 键 | 允许类型 / 取值 | 缺省 | 备注 |
|---|---|---|---|
| `providers` | **必填**，非空数组；每项 `{ kind: 非空字符串, options?: 对象, priority?: 整数 }` | 无（**必填**） | `kind` 须为宿主上**已注册**的 provider（`local` / `s3` 内置；其余由接入方提供，如经 `providerPlugins`）。插件**不**预检 `kind` 有效性——由宿主抛错。`priority` 为整数原样透传；后端选择语义归宿主。 |
| `providerPlugins` | 数组；每项 `{ kind: 非空字符串, create: 函数 }` | `[]` | provider 工厂注册表：`create(options) -> provider`。**非空时**宿主必须暴露 `registerProvider`（Python `register_provider`）。插件**不**预检 `kind` 冲突——由宿主注册表处置。 |
| `schemas` | 数组 \| `null` \| `false` | `[]` | **待注册 schema 定义的注入点**（库不内置权威资源 schema）。数组项须为含非空字符串 `name` 的对象，按序注册（幂等）；`null` / `false` / 缺省 → **不注册任何表**。业务实体 schema 不在此列——由业务持有。 |
| `url` | 对象 | `{}` | 原样透传给 `configureResource`。 |
| `sign` | 函数 \| `null` | `null` | 原样透传给 `configureResource`。 |
| `schema` | 对象 | `{ resource: 'Resource', location: 'ResourceLocation', binding: 'ResourceBinding' }` | 三个 schema 名映射；原样透传给 `configureResource`。 |
| `fields` | 对象 | canonical（见上） | 三表**逻辑角色 → 物理字段**映射；原样透传给 `configureResource`（见 §12）。**仅当提供时**才透传（缺省：不透传 → 宿主用 canonical，逐字节兼容）。 |

**`providers` 为必填。** 若缺失或为空，`capability.create` 在做任何事之前先抛错（消息含 `providers`，零门面调用）。这是刻意的快速失败。

## 12. `fields` 映射

`fields` 把每张资源表的**逻辑角色**映射到**物理列名**，让业务在不触碰插件或通用代码的前提下重命名列。它以 `configureResource({ fields })` 传给宿主。省略的表 / 角色回落为 canonical 名。

| 表 | 必填角色 | 可选角色 |
|---|---|---|
| `resource` | `sha1` | `fileName`、`mime`、`size`、`kind` |
| `location` | `resourceId`、`backend`、`key` | `status`、`priority` |
| `binding` | `resourceId`、`businessTable`、`businessId` | `userId` |

校验规则（构造期强制，消息含表 / 角色名）：

- 未知表 → 抛错；已知表内的未知角色 → 抛错；
- **必填**角色的值必须为**非空字符串**（`null` / `""` / 非字符串 → 抛错）；
- **可选**角色的值必须为非空字符串**或 `null`**——`null` 意为「跳过该列」（不落库）；
- `_id` **不可映射**（它是 core 身份；去重按 `_id`）。

示例——`sha1`→`contentHash`、`fileName`→`name`、`mime`→`contentType`，丢弃 `size`/`kind`；`backend`→`store`、`key`→`objectKey`，丢弃 `status`；`businessTable`→`entity`，丢弃 `userId`：

```jsonc
"fields": {
  "resource": { "sha1": "contentHash", "fileName": "name", "mime": "contentType", "size": null, "kind": null },
  "location": { "backend": "store", "key": "objectKey", "status": null },
  "binding": { "businessTable": "entity", "userId": null }
}
```

`start()` 之后，宿主的 `configureResource` 恰好收到上述对象（由 `capability.fields_passthrough` 用例验证）。

## 13. DDL 边界

插件**不建表**。是否建表、建哪些表由接入方决定（用业务既有的 `syncSchema`（Node）/ `load_defs`（Python））。`opts.schemas` 只把定义 `register` 进宿主 schema 注册表（好让 `configureResource` 的 `schema` 名映射能引用它们）——它**绝不触发 DDL**。

## 14. 错误映射

| 情形 | 插件行为 |
|---|---|
| `download` —— 记录缺引用字段，或引用为空 | 抛普通 **`Error`**（中文消息，**无 `ERR_` 前缀**） |
| `uploadResolver` —— 请求体为空，或 `resourcePut` 未返回 `resourceId` | 抛普通 **`Error`**（中文消息，**无 `ERR_` 前缀**） |
| `capability.create` —— 配置非法（未知顶层键 / 类型错误 / 缺门面方法 / `fields` 未知表或角色，或必填角色非非空字符串） | 抛 `Error`，消息含该字段 / 方法 / 表 / 角色名 |
| `resourceOpen` —— 未找到，或底层读取失败 | 宿主抛错；插件**原样传播，从不捕获或改写** |

- 插件**不**产出任何 HTTP 状态码 / 错误名（`404` / `NOT_FOUND` / `ERR_*` / `500` 在插件源码中一律禁用；conformance 机检强制执行）。
- 下载语义「记录不存在或 `fileField` 为空 → `404 NOT_FOUND`」属于**既有 store-api 皮肤**——不属本插件。
- 跨运行时说明：抛出类在 Node 为 `Error`、在 Python 为 `ValueError`；双端测试均断言消息子串，而非类名。

## 15. 场景事例

每个场景遵循同一四段式：**业务背景 → 配置 / 调用 → 结果 → 优势所在。**

### 场景 1 —— 本地 / 开发环境的头像上传（minio 或 `s3-compat`，path-style）

- **业务背景。** 一个用户资料服务允许用户上传头像。本地 / 开发环境没有云 bucket，只有自托管 MinIO（或任意 path-style 的 S3 兼容网关）。
- **配置 / 调用。**
  ```js
  const { capability, adapter, providers } = require('store-resource-bootstrap-node');

  const handle = capability.create(store, {
    providers: [{
      kind: 'minio',
      options: { bucket: 'avatars', endpoint: 'http://minio:9000', prefix: 'users' },
      priority: 0,
    }],
    providerPlugins: [{ kind: 'minio', create: providers.minio.create }],
    schemas: capability.schemas(),   // 注册三张可选参考表
  });
  await handle.start();

  const uploadResolver = adapter.uploadResolver(store, { kind: 'avatar' });
  // 把 uploadResolver 接入 store-api 的 POST /{resource}/:id/file
  ```
- **结果。** `start()` 返回 `{ registered: ['Resource','ResourceLocation','ResourceBinding'], skipped: [], providerRegistered: ['minio'] }`。minio 预设强制 `forcePathStyle: true`，故客户端以路径寻址 bucket（`http://minio:9000/avatars/...`）。一次上传（`Body: <bytes>`、`ContentType` 取自 `req.query.mime`）经 `resourcePut` 写入数据层。
- **优势所在。** 开发与生产使用同一 `store-api` 接缝；只改 `providers` 项。自托管 MinIO 凭 `forcePathStyle` 预设开箱即用——无需自定义存储适配器、业务代码无条件分支、无新增 HTTP 路由。

### 场景 2 —— 从 OSS 下载报表附件（virtual-hosted）

- **业务背景。** 一个报表服务把生成的报表附件存入阿里云 OSS，并让用户下载。
- **配置 / 调用。**
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
  // 把 fileResolver 接入 store-api 的 GET /{resource}/:id/file
  ```
- **结果。** OSS 预设强制 `forcePathStyle: false`（virtual-hosted，bucket 在域名中）。对形如 `{ file: 'ref1' }` 的记录执行 `GET /{resource}/:id/file`，会产生一次 `resourceOpen('ref1', {})` 并向皮肤返回 `{ body, contentType, fileName }`。若宿主返回 `mime: null`，`contentType` 兜底为 `application/octet-stream`。
- **优势所在。** OSS 特有的寻址要求（仅 virtual-hosted）被封装在预设里——业务无需知道 path-style 与 virtual-hosted 之别。Node 上 SigV4 无需额外配置即可工作；Python 上 OSS 预设自动提供所需的 V2 签名。

### 场景 3 —— 多 provider 并存，按用途分派（经 `order`）

- **业务背景。** 一个服务把体小、热点的头像留在本地后端，把大体量报表归档到远端对象存储。读取应按用途偏好对应后端。
- **配置 / 调用。**
  ```js
  const handle = capability.create(store, {
    providers: [
      { kind: 'local', options: { root: '/data/resources' }, priority: 1 },
      { kind: 'oss', options: { bucket: 'reports' }, priority: 0 },
    ],
  });
  await handle.start();

  // 报表下载：偏好 OSS 后端
  const reportResolver = adapter.download(store, { order: ['oss'] });
  // 头像下载：偏好本地后端
  const avatarResolver = adapter.download(store, { order: ['local'] });
  ```
- **结果。** 整个 `providers` 数组原样传给 `configureResource`，构建一个资源池。读取时 `order` 提示被转发给 `resourceOpen(ref, { order })`——例如报表 resolver 发出 `resourceOpen('ref', { order: ['oss'] })`，本地 resolver 发出 `resourceOpen('ref', { order: ['local'] })`。
- **优势所在。** 多个存储后端共享一条统一、齐整的下载接缝；「用哪个后端」是每 resolver 的 `order` 提示，而非硬编码分支。插件不介入排序语义——它转发提示，交由宿主资源能力决定。

### 场景 4 —— 装配 `url` / `sign`（URL 基址与签名接缝）

- **业务背景。** 资源 URL 须经 CDN 基址分发，链接可能需签名。URL 拼接与签名是宿主 / 业务持有的策略。
- **配置 / 调用。**
  ```js
  const handle = capability.create(store, {
    providers: [{ kind: 'oss', options: { bucket: 'assets' } }],
    url: { base: 'https://cdn.example.com' },
    sign: (resource) => mySigner(resource),
  });
  await handle.start();
  ```
- **结果。** `start()` 把 `url` 与 `sign` **原样**透传给 `store.configureResource`（即 `{ url: { base: 'https://cdn.example.com' }, sign: <fn> }`）；URL 拼接 / 签名由宿主资源能力持有。若省略 `url` / `sign`，则转发缺省值 `{}` / `null`。
- **优势所在。** 插件是纯配置导管——CDN 基址与签名策略可替换或扩展而不改插件，插件也从不重写 URL 逻辑（URL 拼接下沉 core，插件不实现其中任何部分）。
- **此处明确不覆盖：** 绕过数据层的预签名直传**不**由本插件提供——上传始终经宿主 `resourcePut`（见 §16 / §17）。

### 场景 5 —— 经 `fields` 重命名物理列而不碰业务代码

- **业务背景。** 业务已持有列名非 canonical 的资源表（如 `contentHash`、`objectKey`、`entity`）。它希望通用上传 / 下载代码对它们原样可用。
- **配置 / 调用。**
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
- **结果。** `configureResource` 恰好收到上述 `fields` 对象。插件只校验**形状**（未知表 / 角色、必填角色类型、可选角色类型）并透传；语义裁定发生在宿主。映射为 `null` 的 `size` / `kind` / `status` / `userId` 不落库。
- **优势所在。** 逻辑到物理的映射完全落在配置里——业务数据模型永不耦合进通用库，列重命名是改一行配置、零代码改动。`null` 约定让某次部署可丢弃其不用的列。

### 场景 6 —— 缺失 `providers` 时在构造期大声失败

- **业务背景。** 某次配置错误的部署忘了提供资源池。接入方希望立刻得知，而非等到首个请求。
- **配置 / 调用。**
  ```js
  capability.create(store, {});                     // 抛错
  capability.create(store, { providers: [] });      // 抛错
  ```
- **结果。** 两次调用均抛消息含 `providers` 的错误——**在任何门面调用之前**（零 `register` / `has` / `configureResource` 调用）。同理，未知顶层键、坏的 `kind` / `options` / `priority`、坏的 `url` / `sign` / `schema`、畸形的 `schemas` 或畸形的 `fields` 都在构造期抛错并零门面调用。
- **优势所在。** 快速失败校验把配置错误暴露在接线时，而非负载下。由于构造在任何宿主交互之前即已校验，坏配置绝不可能留下半接线的资源池。

### 场景 7 —— 与 store-api 文件子路由配合

- **业务背景。** 皮肤（`store-api`）已暴露资源字节子路由 `GET` / `POST /{resource}/:id/file`。业务希望字节经它流动，而不新写路由。
- **配置 / 调用。**
  ```js
  const { capability, adapter } = require('store-resource-bootstrap-node');

  await capability.create(store, {
    providers: [{ kind: 'local', options: { root: '/data/resources' } }],
  }).start();

  const fileResolver = adapter.download(store);          // 用于 GET  /{resource}/:id/file
  const uploadResolver = adapter.uploadResolver(store);  // 用于 POST /{resource}/:id/file
  // 将二者传入 store-api 皮肤接线
  ```
- **结果。** `GET /{resource}/:id/file` 调用 `fileResolver(req, rec, id)` 并返回字节流带 `content-type` / `content-disposition`（非 JSON）；引用缺失 / 为空变成皮肤的 `404 NOT_FOUND`。`POST /{resource}/:id/file` 调用 `uploadResolver(req, rec, id)`，经 `resourcePut` 中转字节，返回 `{ ref }` 以便皮肤把引用写回记录。
- **优势所在。** 插件不新增任何 HTTP 路由、不产自己的状态码——它对称地接入既有接缝（上传与下载同为 `(req, rec, id)` 形状），故皮肤保持纯传输器，业务写零 HTTP 代码。

## 16. 定制化 / 扩展点

- **自带 provider。** 实现工厂 `create(options) -> provider` 并经 `providerPlugins` 注册；随后在 `providers` 中引用其 `kind`。插件在 `configureResource` **之前**经 `registerProvider`（Python `register_provider`）把各工厂注册到宿主，并在 `start()` 的 `providerRegistered` 中报告已注册 kind。当 `providerPlugins` 非空时，宿主必须暴露该门面。
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
- **直接使用随包的 S3 兼容基。** `oss` 与 `minio` 均为共享 `s3-compat` 基之上的薄预设。若你需要一个缺省 `kind: 's3'` 的裸 S3 兼容 provider，深导入该基（`src/providers/s3-compat`（Node）/ `providers.s3_compat`（Python））并调用其 `create`。它刻意**不**属于公开 `providers` 命名空间（后者仅导出 `oss` 与 `minio`）。
- **自带 schema。** `opts.schemas` 是通用注入点：传自有定义（它们被深拷贝并按序注册），或传 `null` / `false` / 不传以注册零表。
- **重塑资源表。** `opts.fields` 把逻辑角色重映射到物理列名（见 §12），使你既有的 schema 可原样复用。

## 17. 边界与非目标

- **无 DDL。** 插件从不建表（§13）。
- **无 HTTP 路由、无状态码、无错误名。** HTTP 暴露只在 `store-api` 皮肤；插件只抛普通 `Error` / `ValueError`。
- **无宿主 / core 导入。** store 实例始终传入；插件不从宿主、皮肤或 core 包导入任何东西。
- **无 SHA-1 / 内容寻址 / URL 拼接。** 这些下沉 core；插件不实现其中任何部分。
- **无直传存储的预签名上传。** 上传始终经宿主 `resourcePut`（`adapter.upload` 为薄透传；`adapter.uploadResolver` 经 `resourcePut` 中转）。插件不生成预签名 URL。
- **首期范围。** 含：带按需注册的可选参考 schema + 面向 **Node / Python** 的接缝适配。本阶段明确**排除**（附依据）：

  | 排除项 | 依据 |
  |---|---|
  | 管理面 | 复用 store-api 既有 CRUD——属增强非前置依赖 |
  | 资源列表 HTTP 面 | 复用 store-api 既有面 |
  | `go` 端 | 首期仅 Node / Python（见逐端契约表） |
  | `store-api` rust | 首期仅 Node / Python |
  | 其它皮肤（GraphQL / gRPC） | 资源能力属**宿主旁路**；HTTP 暴露只在 store-api |

  「排除」≠「不支持」：纳入时机锚点为 go 生态成熟与 gateway 开关落地；本阶段**不预留代码**。

## 18. FAQ

**Q1. 插件会替我建资源表吗？**
不会。它从不执行 DDL。`capability.schemas()` 只是*返回*可选参考定义；`opts.schemas` 只把它们 `register` 进宿主 schema 注册表。建表由你负责（业务既有的 `syncSchema`（Node）/ `load_defs`（Python））。

**Q2. 省略 `providers` 会怎样？**
`capability.create` 立即抛消息含 `providers` 的错误，零门面调用。`providers` 是唯一必填键。

**Q3. 允许的七个配置键是什么？**
`providers`、`providerPlugins`、`schemas`、`url`、`sign`、`schema`、`fields`。任何其它顶层键抛错。

**Q4. 我必须用 `capability.schemas()` 吗？**
不必。`schemas` 缺省 `[]`（不注册任何表）。你可传内置可选参考集、自有定义，或 `null` / `false` 以不注册任何表。

**Q5. `download` 需要宿主上的 `queryOne` 门面吗？**
不需要。`download` 仅经 `resourceOpen` 读取字节**与**元数据（`fileName` / `mime`）；无 `queryOne` 的宿主也没问题。当返回的 `mime` / `fileName` 为 `null` 时，resolver 兜底为 `application/octet-stream` / 引用字符串。

**Q6. `download` 读取引用的哪一列？**
缺省为记录上名为 `file` 的字段。用 `opts.field` 覆盖（支持 `images.original` 之类点路径），或按请求用 `?field` 覆盖，后者优先于构造期 `field`。

**Q7. 如何重命名资源表列？**
用 `opts.fields` 映射逻辑角色 → 物理列名（见 §12）。必填角色须为非空字符串；可选角色可为非空字符串或 `null`（跳过该列）。`_id` 不可映射。

**Q8. `oss` 与 `minio` 是真实现还是仅别名？**
二者都是构建在共享 `s3-compat` 基之上的真实 S3 兼容实现。`oss` 强制 virtual-hosted（`forcePathStyle: false`）并在 Python 上强制 V2 签名；`minio` 强制 path-style（`forcePathStyle: true`）。

**Q9. 我需要安装 `@aws-sdk/client-s3` / `boto3` 吗？**
仅当你实际使用 `oss` / `minio` provider 时。它们是可选、懒加载的——未安装时包导入与 `capability` / `adapter` 命名空间照常工作；仅调用某 provider 的 `create()` 时抛错。

**Q10. 插件会生成用于直传的预签名 URL 吗？**
不会。上传经宿主 `resourcePut`（`adapter.upload` 为薄透传；`adapter.uploadResolver` 经 `resourcePut` 中转）。预签名直传是非目标。

**Q11. `start()` 调用两次安全吗？**
安全。它幂等：首次调用生效 `schemas` 被 `registered`；后续调用在 `skipped` 中报告它们且 `registered` 为空。`configureResource` 每次 `start()` 调用一次。`reload()` 就是再跑一次 `start()`。

**Q12. 抛的是哪个错误类？**
Node 为 `Error`，Python 为 `ValueError`。消息为普通文本（无 `ERR_` 前缀、无状态码）；双端测试均断言消息子串。

## 19. 开发

```bash
# Node：单测 + conformance 用例
cd node && npm i && npm test          # 运行 `node --test`

# Python：单测 + conformance 用例
cd py && pip install -e ".[dev]" && pytest
```

**流程。** spec 为唯一事实源 → 双端据其实现 → [`conformance/cases.json`](./conformance/cases.json) 由**双端**加载为共享对拍语料（期望值绝不在两端各自复制）。每个运行时测试套件内嵌一项机检，冻结已发布源码，禁止出现：禁用字样（`404` / `NOT_FOUND` / `ERR_` / `500`）、禁用宿主引用（`require('nodejs-store')` / `from py_store`）、禁用调用（`createHash` / `hashlib` / `resourceComposeUrl`）。

## 20. 相关项目

| 项目 | 关系 |
|---|---|
| [`nodejs-store`](../nodejs-store) | Node 宿主；持有本插件所配置的资源能力（`configureResource`、`resourceOpen`、`resourcePut`） |
| [`py-store`](../py-store) | Python 宿主（与 `nodejs-store` 同构） |
| [`store-api`](../store-api) | 本插件所填充的 `fileResolver` / `uploadResolver` 接缝所属皮肤；暴露 `GET` / `POST /{resource}/:id/file` |
| [`store-rbac-bootstrap`](../store-rbac-bootstrap) | 本包所复刻的插件范式（读配置 → 挂接既有接缝） |

## 21. License

MIT。Copyright (c) 2026 丁滔（见 [`LICENSE`](./LICENSE)）。两个包均声明 `MIT`——见 `node/package.json`（`"license": "MIT"`）与 `py/pyproject.toml`（`license = { text = "MIT" }`）。

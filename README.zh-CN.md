# store-resource-bootstrap

common-store 数据层家族（宿主 [nodejs-store](../nodejs-store) / [py-store](../py-store)）的**可选资源引导插件**：

| 关注点 | 宿主包 | 接缝 |
|---|---|---|
| 能力引导 | nodejs-store（node / py） | `register` / `has` / `configureResource`（`configure_resource`） |
| 接缝适配 | store-api（node / py） | `fileResolver` / `file_resolver`（GET `/{resource}/:id/file`） |

> English: [README.md](./README.md)

## 1. 定位

插件只做两件事，别的一概不做：

1. **能力引导** —— 按接入方**注入**的 schema 定义（`schemas`，可选；缺省不注册任何表）注册进宿主 store，并调宿主 store 既有 `configureResource({ providers, url, sign, schema, fields })`；
2. **接缝适配** —— 产出 store-api 所需的 `fileResolver`（`download`）、`uploadResolver`（上传接缝）与薄透传的 `resourcePut`（`upload`）。

**schema 归属**：库**不内置权威资源 schema**——业务实体 schema（如 `product.images` / `user.avatar`）由业务上层定义，库零涉足；资源三表（`Resource` / `ResourceLocation` / `ResourceBinding`，属资源能力自身的持久化模型）仅作**可选参考定义**随包提供（`capability.schemas()`），是否注册由 `opts.schemas` 决定（缺省不注册）。**资源三表的字段结构同样任业务自定义**：三表列名**不写死在宿主**，由接入方经 `opts.fields` 的「逻辑角色 → 物理字段名」映射声明（缺省 = canonical 列名）；库只封装上传 / 下载 / 存储这些**通用代码**，字段命名与结构交业务上层定义，业务数据模型不耦合进通用库。

三条铁律：**零语义发明、零宿主依赖、零回归**。插件不 `require` / `import` 任何宿主、皮肤或 core 包（**默认无任何第三方运行时依赖**；可选参考 provider 模块 `oss` / `minio` 需 S3 兼容 SDK，声明为**可选依赖**、**懒加载**——未安装时模块可装载、`capability` / `adapter` 与测试均不受影响，仅实际调用其 `create()` 时报错）、不发明错误前缀 / 状态码（只抛普通错误）、不触碰任何兄弟仓库。对外暴露双命名空间 `capability` 与 `adapter`，另随包提供**可选参考 provider 命名空间** `providers`（`oss` / `minio`，S3 兼容预设；SDK 懒加载），供接入方在 `providerPlugins` 中直接引用。唯一事实源是 [`spec/00-protocol.md`](./spec/00-protocol.md)。

## 2. 快速上手

### Node（`store-resource-bootstrap-node`）

```js
const { init, store } = require('nodejs-store');       // 宿主 store（由接入方提供）
const { capability, adapter } = require('store-resource-bootstrap-node');

// 能力引导：按需注入 schema 定义（此处用内置可选参考三表）+ 装配资源池
const handle = capability.create(store, {
  providers: [{ kind: 'local', options: { root: '/data/resources' }, priority: 0 }],
  schemas: capability.schemas(),  // 缺省不注册任何表；业务可换传自有定义
});
await handle.start();
// await handle.reload();  // 再跑一次 start()（宿主按整体替换资源池）

// 接缝适配：store-api fileResolver（GET /{resource}/:id/file）
const fileResolver = adapter.download(store);
// const put = adapter.upload(store);  // 薄透传 store.resourcePut(input)
// 接缝适配：store-api uploadResolver（POST /{resource}/:id/file）
const uploadResolver = adapter.uploadResolver(store);
```

### Python（`store-resource-bootstrap-py`）

```python
import asyncio
from py_store import init, store                        # 宿主 store（由接入方提供）
from store_resource_bootstrap import capability, adapter

async def main():
    handle = capability.create(store, {
        "providers": [{"kind": "local", "options": {"root": "/data/resources"}, "priority": 0}],
        "schemas": capability.schemas(),  # 缺省不注册任何表；业务可换传自有定义
    })
    await handle.start()
    # await handle.reload()

    file_resolver = adapter.download(store)
    # put = adapter.upload(store)  # 薄透传 store.resource_put(**input)
    upload_resolver = adapter.upload_resolver(store)

asyncio.run(main())
```

## 3. 配置形状

```jsonc
{
  "providers": [ { "kind": "local", "options": { "root": "/data/resources" }, "priority": 0 } ],
  "providerPlugins": [ { "kind": "oss", "create": "<provider 工厂函数 create(options)>" } ],  // 可选；缺省 []
  "schemas": [ "<schema 定义，见 spec 附录 A / capability.schemas()>" ],  // 可选；缺省 []（不注册任何表）
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
| `schemas` | 数组 \| `null` \| `false` | `[]` | **注册进宿主的 schema 定义注入点**（库不内置权威 schema）。数组逐项须为对象且 `name` 非空字符串，按序 `register`（幂等）；`null` / `false` / 缺省 → **不注册任何表**。业务实体 schema 不在此列，由业务自管 |
| `url` | 对象 | `{}` | 原样传 `configureResource` |
| `sign` | 函数 \| `null` | `null` | 原样传 `configureResource` |
| `schema` | 对象 | `{resource:'Resource',location:'ResourceLocation',binding:'ResourceBinding'}` | 三 schema 名映射；原样传 `configureResource` |
| `fields` | 对象 | canonical（见上） | 三表**逻辑角色 → 物理字段名**映射；原样传 `configureResource({fields})`，使资源三表字段结构由业务自定义。校验：未知表 / 未知角色 → 抛错；**必填角色**（`resource.sha1`、`location.resourceId`/`backend`/`key`、`binding.resourceId`/`businessTable`/`businessId`）须为非空字符串；**可选角色**为非空字符串或 `null`（`null` = 跳过该列不落库）。`_id` 不可映射（core 身份，去重按 `_id`）。**仅在提供该键时**才透传（缺省不传 → 宿主用 canonical，逐字节兼容） |

顶层仅允许上述七个键；出现未知键即配置错误（抛错，绝不静默忽略）。完整契约见 [`spec/00-protocol.md`](./spec/00-protocol.md) §配置形状 / §引导规则。DDL 边界：插件**不建表**——是否建表、建哪些表由接入方决定（业务既有 `syncSchema`（node）/ `load_defs`（py））；`schemas` 只把定义 `register` 进宿主 schema 注册表，不触发 DDL。

## 4. 逐端契约表

| 能力 · 端 | 签名 | 返回 / 语义 |
|---|---|---|
| `capability.schemas` · node | `schemas()` | `Array<object>`：内置**可选参考**定义（三表**深拷贝**，调用方改写不影响内部；库不据此强制注册） |
| `capability.schemas` · py | `schemas()` | `list[dict]`（同上，深拷贝） |
| `capability.create` · node | `create(store, opts)` | `{ async start(), async reload() }` |
| `capability.create` · py | `create(store, opts=None)` | `_Handle`，具 `async start()` / `async reload()`；`opts` 键与 node **同构**（camelCase：`providers`/`providerPlugins`/`schemas`/`url`/`sign`/`schema`/`fields`） |
| `adapter.download` · node | `download(store, opts = {})` → `async (req, rec, id) => {body, contentType, fileName}` | store-api `fileResolver` 契约；**camelCase 键**（对齐 `store-api/node` 既有读取）。字节 + 元数据只经 `resourceOpen`：`mime` / `fileName` 为 `null` 时 `contentType` / `fileName` 兜底（插件不再调 `queryOne`） |
| `adapter.download` · py | `download(store, opts=None)` → `async (request, rec, rid) -> dict` | store-api py `file_resolver` 契约；`opts` 键同 node（`field` / `order`）；**camelCase 键**（对齐 `store-api/py` 的 `out.get("contentType")` / `out.get("fileName")`）。同 node：只经 `resource_open` 读取，不调 `query_one` |
| `adapter.upload` · node | `upload(store)` → `async (input) => store.resourcePut(input)` | 薄透传，不改写入参/出参 |
| `adapter.upload` · py | `upload(store)` → `async (input: dict) => await store.resource_put(**input)` | 薄透传，`input` 键为 py 原生（`file_name` / `mime` / `kind` / `bind` / `bytes`） |
| `adapter.uploadResolver` · node | `uploadResolver(store, opts = {})` → `async (req, rec, id) => { ref }` | store-api `uploadResolver` 契约；`req.body` 为皮已缓冲的 `Buffer` |
| `adapter.uploadResolver` · py | `upload_resolver(store, opts=None)` → `async (request, rec, rid) -> dict` | store-api py `upload_resolver` 契约；`request` 兼容 Starlette Request / dict；`opts` 键同 node（`kind` / `bind`） |

`start()` 固定序列（node；py 同构，门面名 snake_case）：① 注册 `providerPlugins`（**同步**，先于 `configureResource`）；② 按 `opts.schemas` 生效集逐表幂等注册（`has` / `register` 为**同步**调用；缺省 `[]` → 本步空转）；③ `await store.configureResource({ providers, url, sign, schema, fields })`（**异步**；`fields` **仅在提供时**才带）；④ 返回 `{ registered: string[], skipped: string[], providerRegistered: string[] }`（可观测，禁静默）。`reload()` ≡ 再跑一次 `start()`。

## 5. 首期范围与不支持项

含：schema 可选参考定义与按需注册 + 接缝适配（双端 node / py）。

首期明确**排除**（附依据）：

| 排除项 | 依据 |
|---|---|
| 管理面 | 复用 store-api 既有 CRUD —— 属增强非前置依赖 |
| 资源列表 HTTP 面 | 复用 store-api 既有面 |
| go 端 | 首期仅 node / py（见逐端契约表） |
| store-api rust | 首期仅 node / py（见逐端契约表） |
| 其它皮肤（GraphQL / gRPC） | 资源能力属**宿主旁路**，HTTP 暴露只在 store-api；在其它皮肤暴露资源面属各自皮肤议题 |

「首期排除」≠「不支持」：纳入时机锚点为 go 生态成熟与 gateway 开关落地；首期**不预留代码**。

## 6. 开发与测试

```bash
node: cd node && npm i && npm test                 # 单测 + conformance 用例
py:   cd py && pip install -e ".[dev]" && pytest  # 单测 + conformance 用例
```

流程：**spec 为唯一事实源** → 双端各自据其实现 → `conformance/cases.json` 由双端加载为共享对拍语料（禁止两端各自复制期望值）。

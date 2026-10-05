# store-resource-bootstrap

common-store 数据层家族（宿主 [nodejs-store](../nodejs-store) / [py-store](../py-store)）的**可选资源引导插件**：

| 关注点 | 宿主包 | 接缝 |
|---|---|---|
| 能力引导 | nodejs-store（node / py） | `register` / `has` / `configureResource`（`configure_resource`） |
| 接缝适配 | store-api（node / py） | `fileResolver` / `file_resolver`（GET `/{resource}/:id/file`） |

> English: [README.md](./README.md)

## 1. 定位

插件只做两件事，别的一概不做：

1. **能力引导** —— 注册资源三 schema `Resource` / `ResourceLocation` / `ResourceBinding`，并调宿主 store 既有 `configureResource({ providers, url, sign, schema })`；
2. **接缝适配** —— 产出 store-api 所需的 `fileResolver`（`download`）、`uploadResolver`（上传接缝）与薄透传的 `resourcePut`（`upload`）。

三条铁律：**零语义发明、零宿主依赖、零回归**。插件不 `require` / `import` 任何宿主、皮肤或 core 包（**默认无任何第三方运行时依赖**；可选参考 provider 模块 `oss` / `minio` 需 S3 兼容 SDK，声明为**可选依赖**、**懒加载**——未安装时模块可装载、`capability` / `adapter` 与测试均不受影响，仅实际调用其 `create()` 时报错）、不发明错误前缀 / 状态码（只抛普通错误）、不触碰任何兄弟仓库。对外暴露双命名空间 `capability` 与 `adapter`，另随包提供**可选参考 provider 命名空间** `providers`（`oss` / `minio`，S3 兼容预设；SDK 懒加载），供接入方在 `providerPlugins` 中直接引用。唯一事实源是 [`spec/00-protocol.md`](./spec/00-protocol.md)。

## 2. 快速上手

### Node（`store-resource-bootstrap-node`）

```js
const { init, store } = require('nodejs-store');       // 宿主 store（由接入方提供）
const { capability, adapter } = require('store-resource-bootstrap-node');

// 能力引导：注册三 schema + 装配资源池
const handle = capability.create(store, {
  providers: [{ kind: 'local', options: { root: '/data/resources' }, priority: 0 }],
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
  "url":  { "base": "https://cdn.example.com" },  // 可选；→ configureResource({url})。缺省 {}
  "sign": null,                                    // 可选；函数或 null。缺省 null → configureResource({sign})
  "schema": { "resource": "Resource", "location": "ResourceLocation", "binding": "ResourceBinding" }  // 可选；缺省宿主同名
}
```

| 字段 | 允许类型 / 取值 | 缺省 | 备注 |
|---|---|---|---|
| `providers` | **必填**，非空数组；每项 `{kind: 非空字符串, options?: 对象, priority?: 整数}` | 无（必填） | `kind` 须为宿主**已注册**的 provider（`local` / `s3` 内置；其余由接入方经宿主自备）。插件**不预检** kind 有效性，交宿主抛错 |
| `providerPlugins` | 数组；每项 `{kind: 非空字符串, create: 函数}` | `[]` | provider 工厂注册表；`create(options) -> provider`。**非空时**要求宿主具 `registerProvider`（py `register_provider`）。插件**不预检** kind 冲突，交宿主注册表处置 |
| `url` | 对象 | `{}` | 原样传 `configureResource` |
| `sign` | 函数 \| `null` | `null` | 原样传 `configureResource` |
| `schema` | 对象 | `{resource:'Resource',location:'ResourceLocation',binding:'ResourceBinding'}` | 三 schema 名映射；原样传 `configureResource` |

顶层仅允许上述五个键；出现未知键即配置错误（抛错，绝不静默忽略）。完整契约见 [`spec/00-protocol.md`](./spec/00-protocol.md) §配置形状 / §引导规则。DDL 边界：插件**不建表**——三表 DDL 由接入方既有 `syncSchema`（node）/ `load_defs`（py）覆盖。

## 4. 逐端契约表

| 能力 · 端 | 签名 | 返回 / 语义 |
|---|---|---|
| `capability.schemas` · node | `schemas()` | `Array<object>`（三表**深拷贝**，调用方改写不影响内部） |
| `capability.schemas` · py | `schemas()` | `list[dict]`（同上，深拷贝） |
| `capability.create` · node | `create(store, opts)` | `{ async start(), async reload() }` |
| `capability.create` · py | `create(store, opts=None)` | `_Handle`，具 `async start()` / `async reload()`；`opts` 键与 node **同构**（camelCase：`providers`/`providerPlugins`/`url`/`sign`/`schema`） |
| `adapter.download` · node | `download(store, opts = {})` → `async (req, rec, id) => {body, contentType, fileName}` | store-api `fileResolver` 契约；**camelCase 键**（对齐 `store-api/node` 既有读取） |
| `adapter.download` · py | `download(store, opts=None)` → `async (request, rec, rid) -> dict` | store-api py `file_resolver` 契约；`opts` 键同 node（`field` / `order`）；**camelCase 键**（对齐 `store-api/py` 的 `out.get("contentType")` / `out.get("fileName")`） |
| `adapter.upload` · node | `upload(store)` → `async (input) => store.resourcePut(input)` | 薄透传，不改写入参/出参 |
| `adapter.upload` · py | `upload(store)` → `async (input: dict) => await store.resource_put(**input)` | 薄透传，`input` 键为 py 原生（`file_name` / `mime` / `kind` / `bind` / `bytes`） |
| `adapter.uploadResolver` · node | `uploadResolver(store, opts = {})` → `async (req, rec, id) => { ref }` | store-api `uploadResolver` 契约；`req.body` 为皮已缓冲的 `Buffer` |
| `adapter.uploadResolver` · py | `upload_resolver(store, opts=None)` → `async (request, rec, rid) -> dict` | store-api py `upload_resolver` 契约；`request` 兼容 Starlette Request / dict；`opts` 键同 node（`kind` / `bind`） |

`start()` 固定序列（node；py 同构，门面名 snake_case）：① 注册 `providerPlugins`（**同步**，先于 `configureResource`）；② 逐表幂等注册（`has` / `register` 为**同步**调用）；③ `await store.configureResource({ providers, url, sign, schema })`（**异步**）；④ 返回 `{ registered: string[], skipped: string[], providerRegistered: string[] }`（可观测，禁静默）。`reload()` ≡ 再跑一次 `start()`。

## 5. 首期范围与不支持项

含：三 schema 引导 + 接缝适配（双端 node / py）。

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

# store-resource-bootstrap

**一个小的装配插件：给 common-store 宿主装上资源能力 —— provider、URL 与签名策略、schema 注册、列映射 —— 并把 store-api 文件子路由需要的那三个 resolver 交出去。**

[![npm](https://img.shields.io/npm/v/store-resource-bootstrap-node.svg)](https://www.npmjs.com/package/store-resource-bootstrap-node)
[![PyPI](https://img.shields.io/pypi/v/store-resource-bootstrap-py.svg)](https://pypi.org/project/store-resource-bootstrap-py/)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/coenddt/store-resource-bootstrap/blob/main/LICENSE)
[![spec](https://img.shields.io/badge/spec-00--protocol-green.svg)](https://github.com/coenddt/store-resource-bootstrap/blob/main/spec/00-protocol.md)

- 两个运行时，一份契约：Node 与 Python 包逐字实现同一份规范。
- 七个配置键，零宿主导入：`store` 实例作为参数传进来。
- 没有 DDL、没有 HTTP 路由、没有状态码：插件负责接线，宿主负责存储，皮负责暴露。

| 运行时 | 包 | 版本 | 导入 | 宿主兼容 | 引擎下限 |
|---|---|---|---|---|---|
| Node | `store-resource-bootstrap-node` | **0.3.4** | `require('store-resource-bootstrap-node')` | `nodejs-store >= 4.3.0`，可选 peer | Node >= 18 |
| Python | `store-resource-bootstrap-py` | **0.3.4** | `from store_resource_bootstrap import capability, adapter` | `py-store >= 4.3.0` 兼容下限 | Python >= 3.10 |

> 英文主 README：[README.md](./README.md)

## 三个服务，三种给文件 URL 签名的方式

设想一个团队在同一套数据层上跑三个服务：资料服务、报表服务、后台服务。每个都长出了自己的文件故事。资料服务对着 CDN 基址手拼 URL，再追加一段会过期的签名。报表服务指向阿里云 OSS bucket，用另一把 key 签名。后台服务在本地开发时，直接从磁盘目录流式读取。

三个仓库，三种下载文件的方式，三处在 bucket 迁移时必须记得的地方。两个服务是 Node，一个是 Python，连同一个想法都要用两种语言写两遍。轮换签名密钥变成三个 PR、三次部署，以及一段三个服务发出互相矛盾 URL 的窗口期。

字节从来不是问题。它们该在哪儿就在哪儿。缺的是一个统一的地方去说：*这些是我的 provider，这是我的 URL 基址，这是我的签名器，这些是我的表和列* —— 然后从另一头拿到同样的三个文件 resolver，给每个服务用。

`store-resource-bootstrap` 就是那个地方。它是宿主既有资源能力之前的一段配置导管，不是新的存储层。

## 它实际做什么

插件做两件事，顺序就是名字的顺序：

1. **能力引导** —— 幂等注册**你注入**的 schema 定义，然后调用宿主既有的资源门面 `configureResource({ providers, url, sign, schema, fields })`。
2. **接缝适配** —— 产出皮所需的 `download` / `upload` / `uploadResolver` 函数，形状正好是 store-api 既有文件子路由期待的样子。

它**不带权威资源 schema**、**不建表**、**不暴露 HTTP 路由**。这三件事分别属于业务、宿主与皮。

| 职责 | 归属 | 本插件做什么 |
|---|---|---|
| 资源池与 provider 注册表 | 宿主 | 声明 `providers`，注册 `providerPlugins` |
| URL 拼接与签名策略 | 宿主 / core | 原样透传 `url` 与 `sign` |
| schema 定义 | 业务，另有一份可选参考集 | 只注册你注入的那份 |
| 资源表列名 | 业务 | 逻辑角色 → 物理列映射 |
| 字节读写 | 宿主 | 解析引用，调 `resourceOpen` / `resourcePut` |
| 文件子路由、状态码、`404` | store-api 皮 | 只产 resolver，永不产状态码 |

## 关键机制

### provider 只声明，不实现

`providers` 是唯一必填键，必须是非空数组，每项为 `{ kind, options?, priority? }`。插件不预检 `kind` 是否存在 —— 宿主注册表会检查并抛错。如果你需要一个宿主没有的 provider，通过 `providerPlugins` 注册它的工厂；这些工厂会**同步地、在 `configureResource` 之前**装好，所以资源池能在同一次调用里解析到它们。

两个 S3 兼容预设随包提供，挂在可选的 `providers` 命名空间下：`oss` 强制 virtual-hosted 寻址，`minio` 强制 path-style。两者都是同一个 `s3-compat` 基座上的薄别名。它们的 SDK（`@aws-sdk/client-s3`、`boto3`）是可选的、懒加载的 —— 不装 SDK 也能导入本包并使用 `capability` / `adapter`；只有调用某个预设的 `create()` 才需要。

### URL 与签名是导管，不是签名器

插件**不拼 URL，也不实现签名算法**。`url`（对象，默认 `{}`）与 `sign`（函数或 `null`，默认 `null`）原样转发给 `configureResource`。引用如何变成 URL、URL 如何签名，属于宿主的资源能力；内容寻址归 core。

这是刻意的。CDN 基址、过期窗口、私钥轮换是部署策略，不是库语义。换签名器是一行配置改动；插件没有观点需要更新。

### schema 你注入，列名你改

`capability.schemas()` 返回三份可选参考定义的**深拷贝** —— `Resource`（`resources`，唯一 `sha1`）、`ResourceLocation`（`resource_locations`，前缀 `rl`）、`ResourceBinding`（`resource_bindings`，前缀 `rb`）。它们是参考资料，不是命令：`opts.schemas` 默认 `[]`，什么都不注册，`null` / `false` 同理。表到底存不存在，是你的 DDL 决定。

一个细节很重要：`Resource.idPrefix` 必须是空字符串。宿主只在 `idPrefix` 为真值时生成 `_id`，生成的 id 会破坏 `resourceId = sha1` 的约定。

`opts.fields` 重命名通用代码会碰到的列。它把每张表的**逻辑角色**映射到**物理列** —— 例如 `sha1 → contentHash`、`key → objectKey`、`businessTable → entity`。必填角色必须是非空字符串；可选角色可以是非空字符串或 `null`，`null` 意为「不落这一列」。`_id` 不可映射。只有提供该键时才转发，所以更早的宿主仍收到逐字节兼容的载荷。

### 三个 resolver，两种形状

| 工厂 | 返回 | 调用方 | 调用宿主 |
|---|---|---|---|
| `adapter.download(store, opts)` | `async (req, rec, id) => { body, contentType, fileName }` | `GET /{resource}/:id/file` | 一次 `resourceOpen` |
| `adapter.uploadResolver(store, opts)` | `async (req, rec, id) => { ref }` | `POST /{resource}/:id/file` | 一次 `resourcePut` |
| `adapter.upload(store)` | `async (input) => resourcePut(input)` | 你既有的写入端点 | 一次 `resourcePut`，不重塑 |

`download` 从 `opts.field` 读取引用（默认 `'file'`，支持 `images.original` 这类点路径）；请求级 `?field` 优先。一次 `resourceOpen` 同时返回字节**和**元数据，所以没有 `queryOne` 的宿主也能用。缺 `mime` 回落 `application/octet-stream`；缺 `fileName` 回落到引用字符串。

`uploadResolver` 接住皮已缓冲的请求体（Node 里是 `Buffer`，Python 里是 Starlette 请求或 dict），把 `bytes`、`kind`、`fileName`、`mime` 以及可选的 `bind` 结果转交给 `resourcePut`，返回 `{ ref }`。插件自身不做任何 IO。

两个运行时都抛普通 `Error` / `ValueError`，消息点名出错的字段或门面。没有 `ERR_*` 前缀，没有 `404`，没有状态码 —— 下载的 `404 NOT_FOUND` 语义属于皮。`resourceOpen` 抛出的错误**原样传播**：插件从不捕获或改写。

## 跑起来

```bash
# Node —— 包名经 node/package.json 0.3.4 核对
npm i store-resource-bootstrap-node

# Python —— 包名经 py/pyproject.toml 0.3.4 核对
pip install store-resource-bootstrap-py
```

下面两段取自 `node/test/adapter.test.js` 与 `py/tests/test_adapter.py`。一个极小的内存 store 顶替宿主，所以不用装别的东西就能跑。

### Node

```javascript
const { capability, adapter } = require('store-resource-bootstrap-node');

// 宿主 store 的替身；生产环境由 nodejs-store 提供。
const store = {
  has: () => false,
  register: (defn) => console.log('register', defn.name),
  configureResource: async (cfg) => console.log('configure', Object.keys(cfg)),
  resourceOpen: async (ref) => ({
    bytes: Buffer.from('hello'), mime: 'text/plain', fileName: 'a.txt',
  }),
  resourcePut: async (input) => ({ resourceId: 'sha1-of-bytes' }),
};

(async () => {
  const handle = capability.create(store, {
    providers: [{ kind: 'local', options: { root: '/data/resources' }, priority: 0 }],
    schemas: capability.schemas(),
  });
  console.log(await handle.start());
  // { registered: ['Resource', 'ResourceLocation', 'ResourceBinding'], skipped: [], providerRegistered: [] }

  const fileResolver = adapter.download(store);
  console.log(await fileResolver({}, { file: 'ref1' }, 'id1'));
  // { body: <Buffer ...>, contentType: 'text/plain', fileName: 'a.txt' }
})();
```

### Python

```python
import asyncio
from store_resource_bootstrap import capability, adapter


class Store:
    """py_store 的替身；只实现插件会碰到的门面。"""

    def has(self, name):
        return False

    def register(self, defn):
        print("register", defn["name"])

    def configure_resource(self, cfg):
        print("configure", sorted(cfg))

    async def resource_open(self, rid, **kw):
        return {"bytes": b"hello", "mime": "text/plain", "fileName": "a.txt"}

    async def resource_put(self, **kw):
        return {"resourceId": "sha1-of-bytes"}


async def main():
    store = Store()
    handle = capability.create(store, {
        "providers": [{"kind": "local", "options": {"root": "/data/resources"}, "priority": 0}],
        "schemas": capability.schemas(),
    })
    print(await handle.start())

    file_resolver = adapter.download(store)
    print(await file_resolver({"headers": {}}, {"file": "ref1"}, "id1"))
    # {'body': b'hello', 'contentType': 'text/plain', 'fileName': 'a.txt'}

asyncio.run(main())
```

两个运行时加载同一份 `conformance/cases.json` 语料。期望值不在两种语言里各存一份；Node 与 Python 一旦不一致，两边套件会挂在同一个用例上。

## 边界：什么时候不要用

- **它不存字节。** `download` 解析引用并调 `resourceOpen`；`uploadResolver` 转交 `resourcePut`。插件里没有文件 IO、临时文件或存储客户端。
- **它不建表。** `opts.schemas` 只把定义注册进宿主的 schema 注册表，让 `configureResource` 的名称映射能引用它们。DDL 仍然归你。
- **它不说 HTTP。** 没有路由、没有状态码、没有错误名。需要公开文件端点，那是 store-api 的 `GET` / `POST /{resource}/:id/file`。
- **它不实现签名或 URL 拼接。** `sign` 是你提供的函数，`url` 是你提供的对象。插件转发两者，什么都不计算。
- **它不签发直传对象存储的预签名上传。** 上传永远经过宿主的 `resourcePut`，保留一条写入路径、一个记录字节的地方。
- **它不导入宿主、core 或皮的包。** 两个宿主都不是运行时依赖：Node 包把 `nodejs-store >= 4.3.0` 声明为可选 peer，Python 包带同样的兼容下限。store 实例永远由外部注入。

## 它在家族里的位置

它是「拥有资源能力的宿主」与「暴露能力的皮」之间的胶合层：`nodejs-store` / `py-store` 存与取，`store-api` 路由，本插件在中间装配配置并产出 resolver。它复刻 `store-rbac-bootstrap` 的范式 —— 读配置、挂进既有接缝、别的什么都不加。

| 仓库 | 关系 |
|---|---|
| [nodejs-store](https://github.com/coenddt/nodejs-store) | Node 宿主；拥有 `configureResource`、`resourceOpen`、`resourcePut` |
| [py-store](https://github.com/coenddt/py-store) | Python 宿主，与 Node 版同构 |
| [store-api](https://github.com/coenddt/store-api) | 皮；暴露文件子路由，拥有 `404` 语义 |
| [store-rbac-bootstrap](https://github.com/coenddt/store-rbac-bootstrap) | 兄弟插件；本包遵循的范式 |

## 一图看懂

```mermaid
flowchart LR
  A[Business config providers url sign fields] --> B[capability create]
  B --> C[Host resource pool]
  C --> D[store-api file sub-route]
  D --> E[adapter download]
  D --> F[adapter uploadResolver]
  E --> C
  F --> C
  G[adapter upload] --> C
```

三句话：配置只写一次，资源池由宿主建；字节只走 `resourcePut` / `resourceOpen`，插件不碰 IO；HTTP 与 404 留在皮里，插件只交出三个 resolver。

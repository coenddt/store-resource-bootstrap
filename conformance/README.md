# conformance — 双端共享一致性用例

`conformance/cases.json` 是 node / py **共享的同一份** 一致性用例（parity 税的可执行形态）：两端各自加载同一文件、各自执行，**期望值不各自复制**。

## 加载方式

- node：`node/test/conformance.test.js` 以 `require('../../conformance/cases.json')` 加载。
- py：`py/tests/test_conformance.py` 以 `json.loads((Path(__file__).parents[2] / "conformance" / "cases.json").read_text(encoding="utf-8"))` 加载。

## 字段含义

| 字段 | 含义 |
|---|---|
| `facades.node` / `facades.py` | 双端门面名一一对应（camelCase ↔ snake_case），用于把 `expected_calls` 里的 node 名翻译成 py 名 |
| `expect_error_class` | 双端错误类差异（node `Error` / py `ValueError`）；测试只断言 `error_contains` 子串，不断言类名 |
| `schemas.names` | 三表名次序（`Resource` / `ResourceLocation` / `ResourceBinding`） |
| `schemas.collections` | 表名 → collection 映射 |
| `schemas.id_prefixes` | 表名 → idPrefix 映射 |
| `schemas.canonical` | 三 schema 全文（**可选参考定义镜像**，与 `spec/00-protocol.md` 附录 A、双端 `schemas.*` 深比较全等；非库内置权威定义） |
| `capability.*.schemas_ref` | 值为 `"canonical"` 时，测试把 `cases.schemas.canonical` 注入该用例 `opts.schemas`（缺省无此键 → 走 `opts` 原样，即不注册） |
| `capability.fresh` | 注入 `schemas_ref: canonical` 后空种子首次 `start()`：注册三表 + `configure_resource` |
| `capability.idempotent` | 注入 `schemas_ref: canonical` + `seed` 全表，再 `start()`：跳过注册、仅 `configure_resource` |
| `capability.defaults` | 缺省 `url` / `sign` / `schema`（且未注入 `schemas`）时的配置形状：**不注册任何表**、仅 `configure_resource` |
| `capability.schemas_disabled` | `opts.schemas = null`：显式关闭注册（0 注册、仅 `configure_resource`） |
| `capability.custom_schemas` | `opts.schemas` 内联自定义定义（`BizAsset`）：**仅注册该定义**（证明库不强制三表） |
| `capability.fields_passthrough` | `opts.fields` 透传：`start()` 后宿主 `configureResource` 收到 `fields`（证明字段映射经插件原样下沉） |
| `capability.invalid` | 构造期非法配置清单（`error_contains` + 期望零门面调用）；含 `fields` 未知表 / 未知角色 / 必填角色空或非串 / 可选角色非法等用例 |
| `adapter.download` / `download_field` / `download_order` | 下载正常路径 / 自定义 `field` / `order` 透传 |
| `adapter.missing_ref` | 缺引用（字段缺失 / 空串 / `null` 记录）须抛错且零资源调用 |
| `adapter.mime_fallback` / `filename_fallback` | `mime` / `fileName` 缺省兜底；期望取自 `resourceOpen` / `resource_open` 返回片段（`open` 成功即带 `fileName` / `mime`，缺失为 `null` → 兜底），**不再另调 `queryOne` / `query_one`** |
| `adapter.upload` | 上传薄透传入参 |
| `adapter.download_dot_path` / `download_request_field` / `upload_resolver` | 点路径下载 / 请求级 `?field` 优先 / 上传接缝工厂（落库入参与返回 `ref`） |
| `machine_checks.forbidden_literals` | 冻结源文件禁止出现的状态码类字样（`404` / `NOT_FOUND` / `ERR_` / `500`） |
| `machine_checks.forbidden_host_refs` | 冻结源文件禁止出现的宿主引用 |
| `machine_checks.forbidden_calls` | 冻结源文件禁止出现的哈希 / URL 拼接调用 |

## 双端差异约定

- 期望值**逐字一致**；仅「错误类 `Error` ↔ `ValueError`、门面名 camelCase ↔ snake_case」以 `{node, py}` / `facades` 映射表达。
- `order` 为**数组**（如 `["local"]`），两端均按数组透传给 `resource_open` / `resourceOpen`（宿主 `open` 内 `list(order) if order else ...`）。
- 三 schema（**可选参考定义**）以 `schemas.canonical` 为镜像做**深比较**（字段顺序不影响，键名 / 类型 / 索引 / relations 须全等）；`schemas_ref` 仅是测试注入约定，不表示库内置权威定义。
- `facades.node` / `facades.py` 只列**插件实际调用的宿主门面**（`configureResource`↔`configure_resource` 等）；`resourceOpen`↔`resource_open` 为字节 + 元数据唯一读取入口，**`queryOne` / `query_one` 已移除**（`open` 成功即附带 `fileName` / `mime`）。

## 新增 case 约定

**先改 `conformance/cases.json`，再改两端测试**（同「先改 spec」铁律）；禁止只更新一端。测试内一律从 `cases.json` 取值，**不得硬编码**三 schema / 投影串 / 门面名。

机检内嵌于双端测试末条（本目录不另设独立脚本）：node 扫 `node/src/*.js`、py 扫 `py/src/store_resource_bootstrap/*.py`，仅冻结**发布源**，不扫 `test/` 与 `conformance/`。

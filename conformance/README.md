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
| `schemas.canonical` | 三 schema 全文（唯一事实源镜像，与 `spec/00-protocol.md` 附录 A、双端 `schemas.*` 深比较全等） |
| `capability.fresh` | 空种子首次 `start()` 的 `opts` / `seed` / `expected_calls` / `expected_return` |
| `capability.idempotent` | 已注册（`seed` 全表）再 `start()`：跳过注册、仅 `configure_resource` |
| `capability.defaults` | 缺省 `url` / `sign` / `schema` 时的配置形状 |
| `capability.invalid` | 构造期非法配置清单（`error_contains` + 期望零门面调用） |
| `adapter.download` / `download_field` / `download_order` | 下载正常路径 / 自定义 `field` / `order` 透传 |
| `adapter.missing_ref` | 缺引用（字段缺失 / 空串 / `null` 记录）须抛错且零资源调用 |
| `adapter.mime_fallback` / `filename_fallback` | `mime` / `fileName` 缺省兜底 |
| `adapter.upload` | 上传薄透传入参 |
| `machine_checks.forbidden_literals` | 冻结源文件禁止出现的状态码类字样（`404` / `NOT_FOUND` / `ERR_` / `500`） |
| `machine_checks.forbidden_host_refs` | 冻结源文件禁止出现的宿主引用 |
| `machine_checks.forbidden_calls` | 冻结源文件禁止出现的哈希 / URL 拼接调用 |

## 双端差异约定

- 期望值**逐字一致**；仅「错误类 `Error` ↔ `ValueError`、门面名 camelCase ↔ snake_case」以 `{node, py}` / `facades` 映射表达。
- `order` 为**数组**（如 `["local"]`），两端均按数组透传给 `resource_open` / `resourceOpen`（宿主 `open` 内 `list(order) if order else ...`）。
- 三 schema 以 `schemas.canonical` 为准做**深比较**（字段顺序不影响，键名 / 类型 / 索引 / relations 须全等）。

## 新增 case 约定

**先改 `conformance/cases.json`，再改两端测试**（同「先改 spec」铁律）；禁止只更新一端。测试内一律从 `cases.json` 取值，**不得硬编码**三 schema / 投影串 / 门面名。

机检内嵌于双端测试末条（本目录不另设独立脚本）：node 扫 `node/src/*.js`、py 扫 `py/src/store_resource_bootstrap/*.py`，仅冻结**发布源**，不扫 `test/` 与 `conformance/`。

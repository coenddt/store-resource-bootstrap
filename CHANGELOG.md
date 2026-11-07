# Changelog

## Unreleased

### Changed（schema 注册接入批量原子 + `unregister` 补偿；错误信息变化）

- **`start()` 注册阶段改为「优先单次 `registerBatch`」**：宿主批量本身原子（构造期先校验，任一错误零副作用）。
  旧宿主无批量门面时回落逐条 `register`，失败后按整份清单重放 `unregister` 补偿（未知 schema 幂等成功），
  不再默认留下半配置。注册仍在 `configureResource` 之后，顺序不变。
- **错误信息与字段语义变化**：`SCHEMA_REGISTER_FAILED` 的 `registered` 从「失败前已注册」改为「补偿后仍残留」，
  新增 `attempted`（本次尝试清单）；message 由 `schema 注册失败: X（已注册: [...]）` 改为
  `schema 注册失败: [A, B]（残留: [...]）`。依赖旧文案或旧字段语义的下游需适配。
- **构造期门面放宽**：`register` 与 `registerBatch` 二者有其一即可创建（旧宿主不受影响）。

### Added（注册失败取证与补偿用例）

- node：C21（旧宿主逐条残留取证）、C22（批量顺序/清单）、C23（批量失败零残留 + 幂等重放）、
  C24（补偿失败如实报残留）、C25（仅 `registerBatch` 可创建）；py 同名用例逐项对应。
- 取证输出（一次性脚本，已删除）：旧逐条实现残留 `["PartialA"]` 且 `unregister` 调用 0 次；
  新实现残留 `[]` 且整份清单被补偿。

### Breaking（start() 固定序列：先 configureResource，再注册 schema）

- **`start()` 门面顺序调整**为：注册 `providerPlugins` → `await configureResource({...})` → 幂等注册 `schemas`。
  - `registerProvider` 是 `configureResource` 的前置且幂等，无法后置；
  - `configureResource` 是唯一可能因宿主语义校验失败的一步（宿主整体替换 `_pool`，失败保留旧池）；
    把它放在 schema 注册**之前** ⇒ 失败时不留「已注册但未配置」的空表。
- node / py 两端逐位一致；`spec/00-protocol.md`、`conformance/cases.json`、`README.md` / `README.en.md` 同步。

### Fixed（参考 schema `read: []` → `read: null`，对齐宿主新语义）

- 宿主 core 已把 `Some([])` 与 `None` 严格区分：`read: []` = 显式拒读（仅 internal / 豁免直通），
  未配置才走 `unconfiguredPolicy`（缺省 open）。参考三表（`Resource` / `ResourceLocation` / `ResourceBinding`）
  与两处关系 `relations.resource.read` 原写 `read: []`，本意是「读不限制」，新语义下会让 bootstrap 出来的表
  对普通角色不可读 ⇒ 全部改为 `read: null`，保持旧版既有行为。
- `write: []` **保留** —— 本意就是显式拒写（资源行只由 internal 上传 / 绑定流程写入），与读姿态不对称属设计内。
- `spec/00-protocol.md` 附录 A、`conformance/cases.json`（canonical 与 `custom_schemas` 用例）同步。

### Added（schema 注册失败可恢复信息）

- **`start()` 的 schema 注册循环加失败包装（node / py 两端）**：宿主无 `unregister`，注册非原子，
  中途失败时前面已注册的表会留在宿主里。现在抛出的错误带 `code = 'SCHEMA_REGISTER_FAILED'`（node）
  与「已注册: [...]」清单（两端消息一致），调用方可据清单清理或重建，不再只看到一句原始错误。
  py 端以 `ValueError` 包装并 `raise ... from e` 保留原始 cause。
- 新增用例：node `capability.test.js` C21（部分失败清单）、`native-read.test.js` 真实 core 零副作用；
  py `test_schema_register_partial_failure_reports_registered`。

### Added

- `node/test/capability.test.js` C19：`configureResource` 抛错时，宿主只收到 `configureResource` 一次调用，
  零 `register`（失败零副作用）；`py/tests/test_capability.py` 对应 C19。
- `node/test/native-read.test.js`（`STORE_NATIVE=1` opt-in，需 MongoDB + 可解析 nodejs-store）：
  `capability.start()` 注册参考三表后普通角色可读；对照 `read: []` 仍被拒。
  `py/tests/test_capability.py` 补结构断言 `test_reference_schema_read_is_unconfigured`。
- `conformance` 的 `fresh` / `custom_schemas` / `provider_plugins` 用例改为按新序列逐位断言。

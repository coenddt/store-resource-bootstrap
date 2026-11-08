# Changelog

## 0.3.5 (2026-11-08)

目标版本 **0.3.5**（全部非破坏）。

### Breaking

- 无（本版全部为非破坏改动）：`start()` 成功路径的返回结构 `{ registered, skipped, providerRegistered }` 与门面调用顺序未变，
  错误码与文案未新增或改写，宿主原有异常对象原样透传，因此本版按补丁版本（0.3.5）归类。

### Changed（schema 注册接入批量原子 + `unregister` 补偿，目标 0.3.5）

- **`start()` 注册阶段改为「优先单次 `registerBatch`」**：宿主批量本身原子（构造期先校验，任一失败零副作用）；
  宿主无批量门面时自动回落逐条 `register`，不需要配置开关，也不因门面缺失而报错。注册仍在 `configureResource` 之后，顺序不变。
- **`configureResource` 前置，保证失败零注册**：`start()` 顺序固定为 `registerProvider`（仅当配置了 `providerPlugins`）→
  `configureResource` → schema 注册。`configureResource` 是唯一可能因宿主语义校验失败的一步（宿主整体替换 `_pool`，失败保留旧池），
  前置后它失败时 schema 零注册，不留「已注册但未配置」的空表。
- **注册失败按整份清单补偿**：失败后对本次 attempted 的整份清单逐名调用 `unregister`（未知 schema 幂等成功），
  不静默留下半配置；宿主无 `unregister` 时无法补偿，如实把残留写进错误。
- **注册失败的错误契约**：补偿干净时**直接透传宿主原错误对象**（对象同一性、`code`、`message` 均不变）；
  仅当补偿后确实仍有残留时，才在原错误对象上附加 `attempted`（本次尝试清单）与 `registered`（残留清单），
  主错误码与文案不动。上一轮的 `SCHEMA_REGISTER_FAILED` 包装已撤销，不再出现该错误码。
- **构造期门面放宽**：schema 注册只需 `register` 与 `registerBatch` 二者有其一即可创建；`registerProvider` 仍按
  `providerPlugins` 是否存在做条件校验（旧宿主不受影响）。

### Added（注册失败取证与补偿用例）

- node：C21（旧宿主逐条残留取证：原错误 + `attempted`/`registered`）、C22（批量顺序/清单）、
  C23（批量失败零残留 + 原错误对象原样透传 + 幂等重放）、C24（补偿失败如实附加残留）、C25（仅 `registerBatch` 可创建）；py 同名用例逐项对应。
- 取证输出（一次性脚本，已删除）：旧逐条实现残留 `["PartialA"]` 且 `unregister` 调用 0 次；
  新实现残留 `[]` 且整份清单被补偿。

### Fixed（参考 schema `read: []` → `read: null`，对齐宿主新语义）

- 宿主 core 已把 `Some([])` 与 `None` 严格区分：`read: []` = 显式拒读（仅 internal / 豁免直通），
  未配置才走 `unconfiguredPolicy`（缺省 open）。参考三表（`Resource` / `ResourceLocation` / `ResourceBinding`）
  与两处关系 `relations.resource.read` 原写 `read: []`，本意是「读不限制」，新语义下会让 bootstrap 出来的表
  对普通角色不可读 ⇒ 全部改为 `read: null`，保持旧版既有行为。
- `write: []` **保留** —— 本意就是显式拒写（资源行只由 internal 上传 / 绑定流程写入），与读姿态不对称属设计内。
- `spec/00-protocol.md` 附录 A、`conformance/cases.json`（canonical 与 `custom_schemas` 用例）同步。

### Added

- `node/test/capability.test.js` C19：`configureResource` 抛错时，宿主只收到 `configureResource` 一次调用，
  零 `register`（失败零副作用）；`py/tests/test_capability.py` 对应 C19。
- `node/test/native-read.test.js`（`STORE_NATIVE=1` opt-in，需 MongoDB + 可解析 nodejs-store）：
  `capability.start()` 注册参考三表后普通角色可读；对照 `read: []` 仍被拒。
  `py/tests/test_capability.py` 补结构断言 `test_reference_schema_read_is_unconfigured`。
- `conformance` 的 `fresh` / `custom_schemas` / `provider_plugins` 用例改为按新序列逐位断言。

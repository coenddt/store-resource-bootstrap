# Changelog

## Unreleased

### Breaking（start() 固定序列：先 configureResource，再注册 schema）

- **`start()` 门面顺序调整**为：注册 `providerPlugins` → `await configureResource({...})` → 幂等注册 `schemas`。
  - `registerProvider` 是 `configureResource` 的前置且幂等，无法后置；
  - `configureResource` 是唯一可能因宿主语义校验失败的一步（宿主整体替换 `_pool`，失败保留旧池）；
    把它放在 schema 注册**之前** ⇒ 失败时不留「已注册但未配置」的空表。
- node / py 两端逐位一致；`spec/00-protocol.md`、`conformance/cases.json`、`README.md` / `README.en.md` 同步。

### Added

- `node/test/capability.test.js` C19：`configureResource` 抛错时，宿主只收到 `configureResource` 一次调用，
  零 `register`（失败零副作用）；`py/tests/test_capability.py` 对应 C19。
- `conformance` 的 `fresh` / `custom_schemas` / `provider_plugins` 用例改为按新序列逐位断言。

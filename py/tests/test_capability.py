"""capability 用例（C1–C13，与 02 node/test/capability.test.js 逐场景对拍）。"""
import asyncio

import pytest

from store_resource_bootstrap import capability
from mock_store import MockStore

NAMES = ["Resource", "ResourceLocation", "ResourceBinding"]
DEFAULT_SCHEMA_MAP = {"resource": "Resource", "location": "ResourceLocation", "binding": "ResourceBinding"}


def run(coro):
    return asyncio.run(coro)


def _store():
    return MockStore()


def _ok_opts(**over):
    opts = {"providers": [{"kind": "local"}]}
    opts.update(over)
    return opts


# ---- C1 / C2 / C3：schemas ----


def test_C1_schemas_count_and_names():
    defs = capability.schemas()
    assert len(defs) == 3
    assert [d["name"] for d in defs] == NAMES


def test_C2_schemas_key_fields():
    r, rl, rb = capability.schemas()
    assert r["idPrefix"] == ""
    assert r["collection"] == "resources"
    assert r["indexes"] == [{"keys": {"sha1": 1}, "options": {"unique": True}}]
    assert rl["idPrefix"] == "rl"
    assert rl["indexes"] == [{"keys": {"resourceId": 1, "backend": 1}, "options": {"unique": True}}]
    assert rb["idPrefix"] == "rb"
    assert rb["indexes"] == [
        {"keys": {"resourceId": 1, "businessTable": 1, "businessId": 1}, "options": {"unique": True}}
    ]


def test_C3_schemas_deep_copy():
    first = capability.schemas()
    first[0]["fields"]["_id"]["type"] = "int"
    assert capability.schemas()[0]["fields"]["_id"]["type"] == "string"


# ---- C4–C8：create 构造期校验 ----


def test_C4_store_missing_facade():
    with pytest.raises(ValueError, match="门面方法"):
        capability.create({}, _ok_opts())


def test_C5_providers_missing_or_empty():
    store = _store()
    with pytest.raises(ValueError, match="providers"):
        capability.create(store)
    with pytest.raises(ValueError, match="providers"):
        capability.create(store, {"providers": []})


def test_C6_provider_item_invalid():
    store = _store()
    with pytest.raises(ValueError):
        capability.create(store, {"providers": [{"kind": ""}]})
    with pytest.raises(ValueError):
        capability.create(store, {"providers": [{"kind": "local", "priority": 1.5}]})
    with pytest.raises(ValueError):
        capability.create(store, {"providers": [{"kind": "local", "options": 1}]})


def test_C7_unknown_opt_key():
    with pytest.raises(ValueError, match="foo"):
        capability.create(_store(), _ok_opts(foo=1))


def test_C8_url_and_sign_invalid():
    store = _store()
    with pytest.raises(ValueError):
        capability.create(store, _ok_opts(url=1))
    with pytest.raises(ValueError):
        capability.create(store, _ok_opts(sign="x"))


# ---- C9–C13：start / reload ----


def test_C9_start_default_registers_nothing():
    store = _store()
    handle = capability.create(store, _ok_opts())
    out = run(handle.start())
    assert [c[0] for c in store.calls] == ["configure_resource"]
    assert out == {"registered": [], "skipped": [], "providerRegistered": []}


def test_C9b_start_with_injected_schemas():
    store = _store()
    handle = capability.create(store, _ok_opts(schemas=capability.schemas()))
    out = run(handle.start())
    # configure_resource 先于 schema 注册：它是唯一可能失败的步骤，前置 ⇒ 失败零 schema 副作用
    assert [c[0] for c in store.calls] == ["configure_resource", "register", "register", "register"]
    assert [c[1] for c in store.calls[1:]] == NAMES
    assert out == {"registered": NAMES, "skipped": [], "providerRegistered": []}


def test_C10_configure_resource_payload():
    store = _store()
    handle = capability.create(store, _ok_opts())
    run(handle.start())
    cfg = store.calls[0][1]
    assert cfg["providers"] == [{"kind": "local"}]
    assert cfg["url"] == {}
    assert cfg["sign"] is None
    assert cfg["schema"] == DEFAULT_SCHEMA_MAP
    assert "fields" not in cfg                 # 未提供 fields 时载荷不带该键


def test_C19_fields_passthrough():
    store = _store()
    fields = {
        "resource": {"sha1": "contentHash", "size": None},
        "location": {"backend": "store", "status": None},
        "binding": {"businessTable": "entity", "userId": None},
    }
    run(capability.create(store, _ok_opts(fields=fields)).start())
    cfg = store.calls[-1][1]
    assert cfg["fields"] == fields             # 提供时逐位一致


def test_C20_fields_invalid():
    base = [("fields", 1, "fields"), ("fields", {"bogus": {}}, "fields"),
            ("fields", {"resource": 1}, "fields"), ("fields", {"resource": {"bogus": "x"}}, "fields"),
            ("fields", {"resource": {"sha1": None}}, "sha1"),
            ("fields", {"location": {"backend": ""}}, "backend"),
            ("fields", {"binding": {"userId": 1}}, "userId")]
    for key, bad, hit in base:
        store = _store()
        with pytest.raises(ValueError, match=hit):
            capability.create(store, _ok_opts(**{key: bad}))
        assert store.calls == []


def test_C11_start_idempotent():
    store = _store()
    handle = capability.create(store, _ok_opts(schemas=capability.schemas()))
    run(handle.start())
    out2 = run(handle.start())
    assert out2 == {"registered": [], "skipped": NAMES, "providerRegistered": []}
    assert len([c for c in store.calls if c[0] == "register"]) == 3
    assert len([c for c in store.calls if c[0] == "configure_resource"]) == 2


def test_C12_reload_equals_start():
    store = _store()
    handle = capability.create(store, _ok_opts(schemas=capability.schemas()))
    run(handle.start())
    run(handle.reload())
    assert len([c for c in store.calls if c[0] == "register"]) == 3
    assert len([c for c in store.calls if c[0] == "configure_resource"]) == 2


def test_C13_provider_kind_not_prechecked():
    store = _store()
    handle = capability.create(store, {"providers": [{"kind": "bogus"}]})
    assert handle is not None


# ---- C14–C16：providerPlugins 条件化门面 ----


class _NoFacade:
    """仅具 register / has / configure_resource，用于验证条件化门面。"""

    def __init__(self):
        self.calls = []

    def has(self, name):
        return False

    def register(self, defn):
        self.calls.append(("register", defn["name"]))

    def configure_resource(self, cfg):
        self.calls.append(("configure_resource", cfg))


def test_C14_provider_plugins_precede_register():
    store = _store()
    fn = lambda o=None: {"kind": "oss", "o": o}
    handle = capability.create(store, {
        "providers": [{"kind": "local"}],
        "providerPlugins": [{"kind": "oss", "create": fn}],
        "schemas": capability.schemas(),
    })
    out = run(handle.start())
    assert [c[0] for c in store.calls] == [
        "register_provider", "configure_resource", "register", "register", "register"
    ]
    assert store.calls[0][1] == "oss"
    assert store.calls[0][2].create is fn
    assert out["providerRegistered"] == ["oss"]


def test_C15_provider_plugins_missing_facade():
    with pytest.raises(ValueError, match="register_provider"):
        capability.create(_NoFacade(), {
            "providers": [{"kind": "local"}],
            "providerPlugins": [{"kind": "oss", "create": lambda o=None: {}}],
        })


def test_C16_no_facade_required_when_absent_or_empty():
    store = _NoFacade()
    capability.create(store, {"providers": [{"kind": "local"}]})                          # 未传
    capability.create(store, {"providers": [{"kind": "local"}], "providerPlugins": []})   # 空数组


# ---- C17–C18：schemas 注入点 ----


def test_C17_schemas_invalid():
    store = _store()
    for bad in (1, [1], [{}]):
        with pytest.raises(ValueError, match="schemas"):
            capability.create(store, _ok_opts(schemas=bad))


def test_C18_custom_schemas_registered_only():
    store = _store()
    defn = {
        "name": "BizAsset", "collection": "biz_assets", "idPrefix": "ba", "timestamps": True,
        # 用例只验证「自定义定义原样透传注册」，read/write 取值不参与断言；
        # 此处保留空名单即「显式拒绝」，与参考 schema 的 read: None 无关。
        "read": [], "write": [], "fields": {"_id": {"type": "string"}}, "relations": {}, "indexes": [],
    }
    handle = capability.create(store, _ok_opts(schemas=[defn]))
    out = run(handle.start())
    assert out["registered"] == ["BizAsset"]
    assert [c[0] for c in store.calls] == ["configure_resource", "register"]
    assert store.calls[1][1] == "BizAsset"


def test_C19_configure_failure_leaves_no_schema_registration():
    """configure_resource 失败 ⇒ schema 零注册（start 失败无半配置）。"""
    store = _store()
    def boom(payload):
        store.calls.append(("configure_resource", payload))
        raise RuntimeError("provider kind 未知")
    store.configure_resource = boom
    handle = capability.create(store, _ok_opts(schemas=capability.schemas()))
    with pytest.raises(RuntimeError, match="provider kind 未知"):
        run(handle.start())
    assert [c[0] for c in store.calls] == ["configure_resource"]


def test_reference_schema_read_is_unconfigured():
    """参考三表：read 未配置（None）= 不限制（走 unconfigured_policy 缺省 open）；
    write 空名单 = 显式拒写；关系读同样未配置。"""
    defs = {d["name"]: d for d in capability.schemas()}
    for name in ("Resource", "ResourceLocation", "ResourceBinding"):
        assert defs[name]["read"] is None
        assert defs[name]["write"] == []
    assert defs["ResourceLocation"]["relations"]["resource"]["read"] is None
    assert defs["ResourceBinding"]["relations"]["resource"]["read"] is None


def test_schema_register_partial_failure_reports_registered():
    """旧宿主（无 register_batch/unregister）：注册非原子，失败时整份清单如实报残留。"""
    store = _store()
    defs = [
        {"name": "PartialA", "collection": "partial_a", "read": None, "write": [],
         "fields": {"_id": {"type": "string"}}, "relations": {}, "indexes": []},
        {"name": "PartialB", "collection": "partial_b", "read": None, "write": [],
         "fields": {"_id": {"type": "string"}}, "relations": {}, "indexes": []},
    ]
    handle = capability.create(store, _ok_opts(schemas=defs))
    original = store.register
    state = {"n": 0}

    def register(defn):
        state["n"] += 1
        if state["n"] == 2:
            raise RuntimeError("注入失败")
        original(defn)

    store.register = register
    with pytest.raises(RuntimeError, match="注入失败") as ei:
        run(handle.start())
    err = ei.value
    # 补偿不可能（旧宿主无 unregister）：原错误原样上抛，只附加残留 / 尝试清单
    assert not hasattr(err, "code"), "不得把错误改包成 SCHEMA_REGISTER_FAILED"
    assert err.registered == ["PartialA", "PartialB"]
    assert err.attempted == ["PartialA", "PartialB"]
    assert store.has("PartialA") and not store.has("PartialB")


PARTIAL_DEFS = [
    {"name": "PartialA", "collection": "partial_a", "read": None, "write": [],
     "fields": {"_id": {"type": "string"}}, "relations": {}, "indexes": []},
    {"name": "PartialB", "collection": "partial_b", "read": None, "write": [],
     "fields": {"_id": {"type": "string"}}, "relations": {}, "indexes": []},
]


def test_schema_register_batch_atomic_and_order():
    """新宿主：单次 register_batch 原子注册，位于 configure_resource 之后。"""
    store = MockStore(batch=True, unregister=True)
    handle = capability.create(store, _ok_opts(schemas=PARTIAL_DEFS))
    result = run(handle.start())
    assert result["registered"] == ["PartialA", "PartialB"]
    names = [c[0] for c in store.calls]
    assert names.index("configure_resource") < names.index("register_batch")
    assert store.has("PartialA") and store.has("PartialB")


def test_schema_register_batch_failure_rolls_back_and_replays():
    """批量失败：整份清单补偿后零残留，原错误原样透传，同一 store 可幂等重放成功。"""
    host_err = RuntimeError("宿主原文案")
    host_err.code = "HOST_REG_X"
    store = MockStore(batch=True, unregister=True, fail_batch=host_err)
    handle = capability.create(store, _ok_opts(schemas=PARTIAL_DEFS))
    with pytest.raises(RuntimeError) as ei:
        run(handle.start())
    err = ei.value
    assert err is host_err, "补偿成功必须原样透传宿主错误对象"
    assert err.code == "HOST_REG_X"                   # 主错误码保持宿主原值
    assert str(err) == "宿主原文案"                     # 主错误文案保持宿主原值
    assert not hasattr(err, "registered") and not hasattr(err, "attempted")
    assert [c[1] for c in store.calls if c[0] == "unregister"] == ["PartialA", "PartialB"]
    assert not store.has("PartialA") and not store.has("PartialB")

    store.unregister("PartialA")                      # 未知 schema 幂等成功
    result = run(handle.start())
    assert result["registered"] == ["PartialA", "PartialB"]
    assert store.has("PartialA") and store.has("PartialB")


def test_schema_register_rollback_failure_reports_residual():
    """补偿失败：原错误上如实附加残留清单，不改写码值与文案。"""
    store = MockStore(batch=True, unregister=True, fail_batch=True, fail_unregister=True)
    handle = capability.create(store, _ok_opts(schemas=PARTIAL_DEFS))
    with pytest.raises(RuntimeError, match="注入失败") as ei:
        run(handle.start())
    err = ei.value
    assert not hasattr(err, "code")
    assert err.registered == ["PartialA", "PartialB"]
    assert err.attempted == ["PartialA", "PartialB"]


def test_create_accepts_batch_only_store():
    """构造期放宽：宿主只提供 register_batch 也可创建。"""
    store = MockStore(batch=True)
    store.register = None
    assert capability.create(store, _ok_opts(schemas=PARTIAL_DEFS)) is not None

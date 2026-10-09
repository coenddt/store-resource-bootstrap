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
    with pytest.raises(ValueError, match="register"):
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
    assert [c[0] for c in store.calls] == ["register", "register", "register", "configure_resource"]
    assert [c[1] for c in store.calls[:3]] == NAMES
    assert out == {"registered": NAMES, "skipped": [], "providerRegistered": []}


def test_C10_configure_resource_payload():
    store = _store()
    handle = capability.create(store, _ok_opts())
    run(handle.start())
    cfg = store.calls[-1][1]
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
        "register_provider", "register", "register", "register", "configure_resource"
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
        "read": [], "write": [], "fields": {"_id": {"type": "string"}}, "relations": {}, "indexes": [],
    }
    handle = capability.create(store, _ok_opts(schemas=[defn]))
    out = run(handle.start())
    assert out["registered"] == ["BizAsset"]
    assert [c[0] for c in store.calls] == ["register", "configure_resource"]
    assert store.calls[0][1] == "BizAsset"

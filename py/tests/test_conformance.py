"""conformance 用例（加载与 node 同一份 conformance/cases.json；期望值不复制）。"""
import asyncio
import json
from pathlib import Path

import pytest

from store_resource_bootstrap import capability, adapter
from mock_store import MockStore

CASES = json.loads((Path(__file__).parents[2] / "conformance" / "cases.json").read_text(encoding="utf-8"))

# 双端门面名映射（node camelCase → py snake_case）
_FACADE_MAP = dict(zip(CASES["facades"]["node"], CASES["facades"]["py"]))


def run(coro):
    return asyncio.run(coro)


def tr(call):
    """[facade, *args] → (py_facade, *args)"""
    return tuple([_FACADE_MAP[call[0]], *call[1:]])


def test_conformance_schemas_canonical_equal():
    got = capability.schemas()
    assert got == CASES["schemas"]["canonical"]
    assert [d["name"] for d in got] == CASES["schemas"]["names"]
    for d in got:
        assert d["collection"] == CASES["schemas"]["collections"][d["name"]]
        assert d["idPrefix"] == CASES["schemas"]["id_prefixes"][d["name"]]


def test_conformance_schemas_deepcopy():
    a = capability.schemas()
    a[0]["fields"]["_id"]["type"] = "number"
    assert capability.schemas()[0]["fields"]["_id"]["type"] == "string"


@pytest.mark.parametrize("key", ["fresh", "idempotent", "defaults"])
def test_conformance_capability_sequences(key):
    entry = CASES["capability"][key]
    store = MockStore(entry["seed"])
    handle = capability.create(store, entry["opts"])
    out = run(handle.start())
    assert store.calls == [tr(c) for c in entry["expected_calls"]]
    assert out == entry["expected_return"]


def test_conformance_capability_provider_plugins():
    entry = CASES["capability"]["provider_plugins"]
    store = MockStore(entry["seed"])
    specs = entry["opts"]["providerPlugins"]
    creates = [(lambda options=None, i=i: {"kind": "stub", "i": i}) for i in range(len(specs))]
    opts = dict(entry["opts"])
    opts["providerPlugins"] = [{"kind": s["kind"], "create": creates[i]} for i, s in enumerate(specs)]

    out = run(capability.create(store, opts).start())

    reg_calls = [c for c in store.calls if c[0] == "register_provider"]
    assert out["providerRegistered"] == entry["expected_registered_kinds"]
    assert len(reg_calls) == len(entry["expected_registered_kinds"])
    for i, c in enumerate(reg_calls):
        assert c[1] == entry["expected_registered_kinds"][i]
        assert c[2].create is creates[i]

    names = [c[0] for c in store.calls]
    assert names.index("register_provider") < names.index("configure_resource")
    assert store.calls[-len(entry["expected_tail_calls"]):] == [tr(c) for c in entry["expected_tail_calls"]]
    for k, v in entry["expected_return_rest"].items():
        assert out[k] == v


def test_conformance_capability_invalid():
    for c in CASES["capability"]["invalid"]:
        store = MockStore()
        with pytest.raises(ValueError) as ei:
            capability.create(store, c["opts"])
        assert c["error_contains"] in str(ei.value), f"{c['name']} 消息应含 {c['error_contains']}"
        assert len(store.calls) == c["expected_call_count"], f"{c['name']} 应零门面调用"


def test_conformance_download_default():
    c = CASES["adapter"]["download"]
    store = MockStore()
    resolve = adapter.download(store, c["opts"])
    out = run(resolve(None, c["record"], "id1"))
    assert store.calls[0] == tr(c["expected_open_call"])
    assert store.calls[1] == tr(c["expected_query_call"])
    assert out["contentType"] == c["expected_result"]["contentType"]
    assert out["fileName"] == c["expected_result"]["fileName"]
    assert out["body"].decode() == c["expected_result"]["body_text"]


def test_conformance_download_field_and_order():
    f = CASES["adapter"]["download_field"]
    s1 = MockStore()
    run(adapter.download(s1, f["opts"])(None, f["record"], "id1"))
    assert s1.calls[0] == tr(f["expected_open_call"])

    o = CASES["adapter"]["download_order"]
    s2 = MockStore()
    run(adapter.download(s2, o["opts"])(None, o["record"], "id1"))
    assert s2.calls[0] == tr(o["expected_open_call"])


def test_conformance_download_missing_ref():
    for c in CASES["adapter"]["missing_ref"]:
        store = MockStore()
        resolve = adapter.download(store, {})
        with pytest.raises(ValueError) as ei:
            run(resolve(None, c["record"], "id1"))
        assert c["error_contains"] in str(ei.value), f"{c['name']} 消息应含 {c['error_contains']}"
        assert len(store.calls) == 0, f"{c['name']} 应零资源调用"


def test_conformance_download_meta_fallbacks():
    m = CASES["adapter"]["mime_fallback"]
    s1 = MockStore()

    async def meta_m(gql, params):
        return dict(m["meta"])

    s1.query_one = meta_m
    o1 = run(adapter.download(s1, {})(None, {"file": "ref1"}, "id1"))
    assert o1["contentType"] == m["expected"]["contentType"]
    assert o1["fileName"] == m["expected"]["fileName"]

    f = CASES["adapter"]["filename_fallback"]
    s2 = MockStore()

    async def meta_f(gql, params):
        return dict(f["meta"])

    s2.query_one = meta_f
    o2 = run(adapter.download(s2, {})(None, {"file": "ref1"}, "id1"))
    assert o2["contentType"] == f["expected"]["contentType"]
    assert o2["fileName"] == f["expected"]["fileName"]


def test_conformance_upload_passthrough():
    entry = CASES["adapter"]["upload"]
    store = MockStore()
    ret = run(adapter.upload(store)(entry["input"]))
    assert store.calls[0] == ("resource_put", entry["input"])
    assert ret == {"resourceId": "sha1", "sha1": "sha1", "locations": []}


def test_conformance_download_dot_path_and_request_field():
    d = CASES["adapter"]["download_dot_path"]
    s1 = MockStore()
    run(adapter.download(s1, d["opts"])(None, d["record"], "id1"))
    assert s1.calls[0] == tr(d["expected_open_call"])

    r = CASES["adapter"]["download_request_field"]
    s2 = MockStore()
    req = _Req(query=r["request_query"])
    run(adapter.download(s2, r["opts"])(req, r["record"], "id1"))
    assert s2.calls[0] == tr(r["expected_open_call"])


class _Req:
    def __init__(self, query=None, headers=None, body=b""):
        self.query_params = dict(query or {})
        self.headers = dict(headers or {})
        self._body = body

    async def body(self):
        return self._body


def test_conformance_upload_resolver():
    c = CASES["adapter"]["upload_resolver"]
    store = MockStore()
    resolve = adapter.upload_resolver(store, c["opts"])
    spec = c["request"]
    req = _Req(query=spec["query"], headers=spec["headers"], body=bytes(spec["body_bytes"]))
    out = run(resolve(req, c["record"], c["record"]["_id"]))
    put = next(x[1] for x in store.calls if x[0] == "resource_put")
    exp = c["expected_put"]["py"]
    assert put["bytes"] == bytes(exp["bytes"])
    assert put["kind"] == exp["kind"]
    assert put["file_name"] == exp["file_name"]
    assert put["mime"] == exp["mime"]
    assert out == {"ref": c["expected_ref"]}


def test_conformance_machine_checks():
    src = Path(__file__).parents[1] / "src" / "store_resource_bootstrap"
    blocked = (
        CASES["machine_checks"]["forbidden_literals"]
        + CASES["machine_checks"]["forbidden_host_refs"]
        + CASES["machine_checks"]["forbidden_calls"]
    )
    hits = 0
    for p in src.glob("*.py"):
        text = p.read_text(encoding="utf-8")
        for token in blocked:
            if token in text:
                hits += 1
    assert hits == 0, f"src 命中禁用字样 {hits} 处"

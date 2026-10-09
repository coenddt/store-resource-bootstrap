"""adapter 用例（D1–D9，与 02 node/test/adapter.test.js 逐场景对拍）。"""
import asyncio

import pytest

from store_resource_bootstrap import adapter
from mock_store import MockStore


def run(coro):
    return asyncio.run(coro)


def _store():
    return MockStore()


def test_D1_download_normal():
    store = _store()
    resolver = adapter.download(store)
    out = run(resolver({"headers": {}}, {"file": "ref1"}, "id1"))
    assert out == {"body": b"hello", "contentType": "text/plain", "fileName": "a.txt"}
    assert store.calls == [("resource_open", "ref1", {})]   # 仅一次 resource_open（不再自建 Resource 查询）


def test_D2_custom_field():
    store = _store()
    resolver = adapter.download(store, {"field": "coverId"})
    run(resolver({"headers": {}}, {"coverId": "ref2"}, "id"))
    assert ("resource_open", "ref2", {}) in store.calls


def test_D3_order_passthrough_as_list():
    store = _store()
    resolver = adapter.download(store, {"order": ["local"]})
    run(resolver({"headers": {}}, {"file": "ref1"}, "id"))
    assert ("resource_open", "ref1", {"order": ["local"]}) in store.calls


def test_D4_missing_ref_field():
    store = _store()
    resolver = adapter.download(store)
    with pytest.raises(ValueError, match="file"):
        run(resolver({"headers": {}}, {}, "id"))
    assert not any(c[0] == "resource_open" for c in store.calls)


def test_D5_empty_ref():
    store = _store()
    resolver = adapter.download(store)
    with pytest.raises(ValueError):
        run(resolver({"headers": {}}, {"file": ""}, "id"))


def test_D6_mime_fallback():
    store = _store()

    async def open_mime_none(rid, **kw):
        return {"bytes": b"hello", "fileName": "a.txt", "mime": None}

    store.resource_open = open_mime_none
    resolver = adapter.download(store)
    out = run(resolver({"headers": {}}, {"file": "ref1"}, "id"))
    assert out["contentType"] == "application/octet-stream"


def test_D7_filename_fallback():
    store = _store()

    async def open_no_name(rid, **kw):
        return {"bytes": b"hello", "mime": "text/plain", "fileName": None}

    store.resource_open = open_no_name
    resolver = adapter.download(store)
    out = run(resolver({"headers": {}}, {"file": "ref9"}, "id"))
    assert out["fileName"] == "ref9"


def test_D8_construction_errors():
    with pytest.raises(ValueError):
        adapter.download(MockStore(), {"field": ""})
    no_query = _store()
    no_query.query_one = None            # 无 query_one 的宿主也应可 download（解耦核心断言）
    assert adapter.download(no_query) is not None
    no_open = _store()
    no_open.resource_open = None
    with pytest.raises(ValueError):
        adapter.download(no_open)


def test_D9_upload_passthrough():
    store = _store()
    upload_ = adapter.upload(store)
    payload = {"sha1": "s1", "size": 3}
    out = run(upload_(payload))
    assert ("resource_put", payload) in store.calls
    assert out == {"resourceId": "sha1", "sha1": "sha1", "locations": []}

    broken = _store()
    broken.resource_put = None
    with pytest.raises(ValueError):
        adapter.upload(broken)


class _Req:
    """conformance / 单测用的最小请求替身（Starlette 形态）。"""

    def __init__(self, query=None, headers=None, body=b""):
        self.query_params = dict(query or {})
        self.headers = dict(headers or {})
        self._body = body

    async def body(self):
        return self._body


def test_D10_dot_path():
    store = _store()
    run(adapter.download(store, {"field": "images.original"})(None, {"images": {"original": "ref3"}}, "id"))
    assert ("resource_open", "ref3", {}) in store.calls


def test_D11_request_field_priority():
    store = _store()
    req = _Req(query={"field": "images.original"})
    run(adapter.download(store, {"field": "file"})(req, {"file": "ref0", "images": {"original": "ref1"}}, "id"))
    assert ("resource_open", "ref1", {}) in store.calls


def test_D12_upload_resolver_normal():
    store = _store()
    req = _Req(query={"fileName": "a.png", "mime": "image/png"}, headers={}, body=b"hi")
    out = run(adapter.upload_resolver(store, {"kind": "image"})(req, {"_id": "ART1"}, "ART1"))
    put = next(c[1] for c in store.calls if c[0] == "resource_put")
    assert put["bytes"] == b"hi" and put["kind"] == "image"
    assert put["file_name"] == "a.png" and put["mime"] == "image/png"
    assert out == {"ref": "sha1"}


def test_D13_upload_resolver_empty_body():
    store = _store()
    with pytest.raises(ValueError, match="上传字节体"):
        run(adapter.upload_resolver(store)(_Req(body=b""), {}, "id"))
    assert not any(c[0] == "resource_put" for c in store.calls)


def test_D14_upload_resolver_construction_errors():
    broken = _store()
    broken.resource_put = None
    with pytest.raises(ValueError):
        adapter.upload_resolver(broken)
    with pytest.raises(ValueError):
        adapter.upload_resolver(_store(), {"kind": ""})
    with pytest.raises(ValueError):
        adapter.upload_resolver(_store(), {"bind": "x"})

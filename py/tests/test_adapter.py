"""adapter 用例（D1–D9，与 02 node/test/adapter.test.js 逐场景对拍）。"""
import asyncio

import pytest

from store_resource_bootstrap import adapter
from mock_store import MockStore

PROJECTION = "Resource($condition: @c0) { _id, fileName, mime }"


def run(coro):
    return asyncio.run(coro)


def _store():
    return MockStore()


def test_D1_download_normal():
    store = _store()
    resolver = adapter.download(store)
    out = run(resolver({"headers": {}}, {"file": "ref1"}, "id1"))
    assert out == {"body": b"hello", "contentType": "text/plain", "fileName": "a.txt"}
    assert ("resource_open", "ref1", {}) in store.calls
    assert ("query_one", PROJECTION, {"c0": {"_id": "ref1"}}) in store.calls


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

    async def query_one_mime_none(gql, params):
        store.calls.append(("query_one", gql, params))
        return {"_id": params["c0"]["_id"], "fileName": "a.txt", "mime": None}

    store.query_one = query_one_mime_none
    resolver = adapter.download(store)
    out = run(resolver({"headers": {}}, {"file": "ref1"}, "id"))
    assert out["contentType"] == "application/octet-stream"


def test_D7_filename_fallback():
    store = _store()

    async def query_one_no_name(gql, params):
        store.calls.append(("query_one", gql, params))
        return {"_id": params["c0"]["_id"], "mime": "text/plain"}

    store.query_one = query_one_no_name
    resolver = adapter.download(store)
    out = run(resolver({"headers": {}}, {"file": "ref9"}, "id"))
    assert out["fileName"] == "ref9"


def test_D8_construction_errors():
    with pytest.raises(ValueError):
        adapter.download(MockStore(), {"field": ""})
    no_query = _store()
    no_query.query_one = None
    with pytest.raises(ValueError):
        adapter.download(no_query)
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

"""记录调用的最小宿主替身；同步门面返回直接值，异步门面返回 awaitable。"""
from __future__ import annotations


class MockStore:
    def __init__(self, seed=None):
        self.calls = []                                  # [("register", name), ("configure_resource", cfg), ...]
        # seed 为表名列表（conformance 传入），仅映射为「已注册」集合
        self.registered = {n: True for n in (seed or [])}

    def has(self, name):
        return name in self.registered

    def register(self, defn):
        self.calls.append(("register", defn["name"]))
        self.registered[defn["name"]] = defn

    def configure_resource(self, cfg):
        self.calls.append(("configure_resource", cfg))
        return {"pool": "stub"}

    async def resource_open(self, rid, **kw):
        self.calls.append(("resource_open", rid, kw))
        return {"bytes": b"hello", "resourceId": rid, "backend": "local", "key": "k"}

    async def resource_put(self, **kw):
        self.calls.append(("resource_put", kw))
        return {"resourceId": "sha1", "sha1": "sha1", "locations": []}

    async def query_one(self, gql, params):
        self.calls.append(("query_one", gql, params))
        return {"_id": params["c0"]["_id"], "fileName": "a.txt", "mime": "text/plain"}

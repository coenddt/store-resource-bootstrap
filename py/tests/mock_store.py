"""记录调用的最小宿主替身；同步门面返回直接值，异步门面返回 awaitable。

关键字参数控制宿主能力（默认均无 = 旧宿主）：batch / unregister / fail_batch（只失败一次）/ fail_unregister。
"""
from __future__ import annotations


class MockStore:
    def __init__(self, seed=None, *, batch=False, unregister=False,
                 fail_batch=False, fail_unregister=False):
        self.calls = []                                  # [("register", name), ("configure_resource", cfg), ...]
        # seed 为表名列表（conformance 传入），仅映射为「已注册」集合
        self.registered = {n: True for n in (seed or [])}
        self._batch_failures = 1 if fail_batch else 0
        self._fail_unregister = fail_unregister
        if unregister:
            self.unregister = self._unregister
        if batch:
            self.register_batch = self._register_batch

    def has(self, name):
        return name in self.registered

    def register(self, defn):
        self.calls.append(("register", defn["name"]))
        self.registered[defn["name"]] = defn

    def configure_resource(self, cfg):
        self.calls.append(("configure_resource", cfg))
        return {"pool": "stub"}

    def register_provider(self, kind, mod):
        self.calls.append(("register_provider", kind, mod))

    def _unregister(self, name):
        self.calls.append(("unregister", name))
        if self._fail_unregister:
            raise RuntimeError("补偿失败")
        self.registered.pop(name, None)

    def _register_batch(self, items, ctx=None):
        self.calls.append(("register_batch", [it["defn"]["name"] for it in items]))
        if self._batch_failures > 0:
            self._batch_failures -= 1
            raise RuntimeError("注入失败")
        for it in items:
            self.registered[it["defn"]["name"]] = it["defn"]

    async def resource_open(self, rid, **kw):
        self.calls.append(("resource_open", rid, kw))
        # 元数据（fileName/mime）由宿主 resource_open 附带返回（下载不再自建 Resource 查询）
        return {"bytes": b"hello", "resourceId": rid, "backend": "local", "key": "k",
                "fileName": "a.txt", "mime": "text/plain"}

    async def resource_put(self, **kw):
        self.calls.append(("resource_put", kw))
        return {"resourceId": "sha1", "sha1": "sha1", "locations": []}

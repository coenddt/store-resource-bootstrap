"""store-resource-bootstrap-py — 资源引导插件包（可选，宿主旁路）。

唯一事实源：spec/00-protocol.md。零判决、零语义发明、零宿主依赖。
两命名空间：capability（能力引导：schemas / create）与 adapter（接缝适配：download / upload）。
"""
from __future__ import annotations

import copy
import inspect
from types import SimpleNamespace

from .schemas import RESOURCE_SCHEMAS
from . import providers as providers

CAPABILITY_FACADES = ("register", "has", "configure_resource")
ALLOWED_OPTS = ("providers", "url", "sign", "schema", "providerPlugins")
DEFAULT_SCHEMA_NAMES = {
    "resource": "Resource",
    "location": "ResourceLocation",
    "binding": "ResourceBinding",
}


async def _call(fn, *args, **kwargs):
    """门面调用：sync 直接调；返回 awaitable（宿主支持 async 门面时）则 await。"""
    out = fn(*args, **kwargs)
    if inspect.isawaitable(out):
        out = await out
    return out


def _assert_store(store, facades, where):
    if store is None:
        raise ValueError(f"{where}: store 必填")
    for name in facades:
        if not callable(getattr(store, name, None)):
            raise ValueError(f"{where}: store 缺少门面方法: {name}")


def _assert_known_keys(opts, where):
    for key in opts:
        if key not in ALLOWED_OPTS:
            raise ValueError(f"{where}: 未知配置键: {key}")


# ---- capability：能力引导 ----


def schemas():
    # 深拷贝：调用方改写不得影响内部定义
    return copy.deepcopy(RESOURCE_SCHEMAS)


class _Handle:
    def __init__(self, store, opts):
        self._store = store
        self._opts = opts

    async def start(self):
        registered = []
        skipped = []
        provider_registered = []
        for spec in self._opts["providerPlugins"]:
            # 宿主 py 端 register_provider 校验 hasattr(mod, "create")，须传具属性对象
            self._store.register_provider(spec["kind"], SimpleNamespace(create=spec["create"]))
            provider_registered.append(spec["kind"])
        for defn in schemas():
            if self._store.has(defn["name"]):      # has 为同步门面
                skipped.append(defn["name"])
            else:
                self._store.register(defn)         # register 为同步门面，幂等
                registered.append(defn["name"])
        await _call(self._store.configure_resource, {
            "providers": self._opts["providers"],
            "url": self._opts["url"],
            "sign": self._opts["sign"],
            "schema": self._opts["schema"],
        })                                          # configure_resource 为同步实现，_call 兼容
        return {"registered": registered, "skipped": skipped, "providerRegistered": provider_registered}

    async def reload(self):
        # 宿主 configure 整体替换 _pool，故 reload ≡ start（无需先清除）
        return await self.start()


def create(store, opts=None):
    _assert_store(store, CAPABILITY_FACADES, "capability.create")
    opts = {} if opts is None else opts
    if not isinstance(opts, dict):
        raise ValueError("capability.create: opts 须为 dict")
    _assert_known_keys(opts, "capability.create")

    providers = opts.get("providers")
    if not isinstance(providers, list) or len(providers) == 0:
        raise ValueError("capability.create: providers 必填且须为非空数组")
    for i, spec in enumerate(providers):
        if not isinstance(spec, dict):
            raise ValueError(f"capability.create: providers[{i}] 须为对象")
        kind = spec.get("kind")
        if not isinstance(kind, str) or kind == "":
            raise ValueError(f"capability.create: providers[{i}].kind 须为非空字符串")
        options = spec.get("options")
        if options is not None and not isinstance(options, dict):
            raise ValueError(f"capability.create: providers[{i}].options 须为对象")
        priority = spec.get("priority")
        if priority is not None and not isinstance(priority, int):
            raise ValueError(f"capability.create: providers[{i}].priority 须为整数")

    url = opts.get("url", {})
    if not isinstance(url, dict):
        raise ValueError("capability.create: url 须为对象")
    sign = opts.get("sign", None)
    if sign is not None and not callable(sign):
        raise ValueError("capability.create: sign 须为函数或 None")
    schema = opts.get("schema", dict(DEFAULT_SCHEMA_NAMES))
    if not isinstance(schema, dict):
        raise ValueError("capability.create: schema 须为对象")
    provider_plugins = opts.get("providerPlugins", [])
    if not isinstance(provider_plugins, list):
        raise ValueError("capability.create: providerPlugins 须为数组")
    for i, spec in enumerate(provider_plugins):
        if not isinstance(spec, dict):
            raise ValueError(f"capability.create: providerPlugins[{i}] 须为对象")
        kind = spec.get("kind")
        if not isinstance(kind, str) or kind == "":
            raise ValueError(f"capability.create: providerPlugins[{i}].kind 须为非空字符串")
        if not callable(spec.get("create")):
            raise ValueError(f"capability.create: providerPlugins[{i}].create 须为函数")
    # 条件化门面校验：仅当有 provider 需要注册时才要求宿主门面（向后兼容旧 store）
    if len(provider_plugins) > 0:
        _assert_store(store, ("register_provider",), "capability.create")

    return _Handle(store, {
        "providers": providers, "url": url, "sign": sign, "schema": schema,
        "providerPlugins": provider_plugins,
    })


# ---- adapter：接缝适配 ----

_RESOURCE_PROJECTION = " { _id, fileName, mime }"  # 投影语法同 store-api/node/src/plugin.js L109


def download(store, opts=None):
    _assert_store(store, ("resource_open", "query_one"), "adapter.download")
    opts = {} if opts is None else opts
    if not isinstance(opts, dict):
        raise ValueError("adapter.download: opts 须为 dict")
    field = opts.get("field", "file")
    if not isinstance(field, str) or field == "":
        raise ValueError("adapter.download: field 须为非空字符串")
    order = opts.get("order")

    # 返回 store-api 既有 file_resolver 契约：(request, rec, rid) -> {body, contentType, fileName}
    async def file_resolver(request, rec, rid):
        ref = None if rec is None else rec.get(field)
        if ref is None or ref == "":
            raise ValueError(f"记录缺少资源引用字段: {field}")
        if order is None:
            opened = await _call(store.resource_open, ref)
        else:
            opened = await _call(store.resource_open, ref, order=order)
        meta = await _call(
            store.query_one,
            f"Resource($condition: @c0){_RESOURCE_PROJECTION}",
            {"c0": {"_id": ref}},
        )
        return {
            "body": opened["bytes"],
            "contentType": (meta or {}).get("mime") or "application/octet-stream",
            "fileName": (meta or {}).get("fileName") or str(ref),
        }

    return file_resolver


def upload(store):
    _assert_store(store, ("resource_put",), "adapter.upload")

    # 薄透传：不改写入参、不改写出参
    async def upload_(input):
        return await _call(store.resource_put, **input)

    return upload_


capability = SimpleNamespace(schemas=schemas, create=create)
adapter = SimpleNamespace(download=download, upload=upload)

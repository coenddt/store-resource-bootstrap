"""store-resource-bootstrap-py — 资源引导插件包（可选，宿主旁路）。

契约依据：spec/00-protocol.md。零判决、零语义发明、零宿主依赖。
两命名空间：capability（能力引导：schemas / create）与 adapter（接缝适配：download / upload）。
"""
from __future__ import annotations

import copy
import inspect
from types import SimpleNamespace

from .schemas import RESOURCE_SCHEMAS
from . import providers as providers

CAPABILITY_FACADES = ("register", "has", "configure_resource")
ALLOWED_OPTS = ("providers", "schemas", "url", "sign", "schema", "fields", "providerPlugins")
DEFAULT_SCHEMA_NAMES = {
    "resource": "Resource",
    "location": "ResourceLocation",
    "binding": "ResourceBinding",
}
# 资源表「逻辑角色」清单（供 fields 形状校验；语义裁决在宿主 configure_resource）
_FIELD_ROLES = {
    "resource": (("sha1",), ("fileName", "mime", "size", "kind")),
    "location": (("resourceId", "backend", "key"), ("status", "priority")),
    "binding": (("resourceId", "businessTable", "businessId"), ("userId",)),
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


def _assert_fields(fields, where):
    """校验 fields 形状（表名 / 角色名 / 值类型）；语义裁决在宿主 configure_resource，本层只做形状"""
    if not isinstance(fields, dict):
        raise ValueError(f"{where}: fields 须为对象")
    for table in fields:
        if table not in _FIELD_ROLES:
            raise ValueError(f"{where}: fields 未知表: {table}")
    for table, (required, optional) in _FIELD_ROLES.items():
        given = fields[table] if table in fields else {}
        if not isinstance(given, dict):
            raise ValueError(f"{where}: fields.{table} 须为对象")
        for role, v in given.items():
            if role not in required and role not in optional:
                raise ValueError(f"{where}: fields.{table} 未知角色: {role}")
            is_str = isinstance(v, str) and v != ""
            if role in required:
                if not is_str:
                    raise ValueError(f"{where}: fields.{table}.{role} 为必填角色，须为非空字符串")
            elif v is not None and not is_str:
                raise ValueError(f"{where}: fields.{table}.{role} 须为非空字符串或 null")


# ---- capability：能力引导 ----


def schemas():
    # 内置「可选参考」定义：库不再把它作为权威 schema 强制注册；
    # 接入方按需 capability.create(store, {"schemas": capability.schemas()}) 注入，
    # 或传入自有定义，或不传（不注册任何表，schema 全交业务/宿主）。
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
        for defn in self._opts["schemas"]:
            if self._store.has(defn["name"]):      # has 为同步门面
                skipped.append(defn["name"])
            else:
                self._store.register(defn)         # register 为同步门面，幂等
                registered.append(defn["name"])
        payload = {
            "providers": self._opts["providers"],
            "url": self._opts["url"],
            "sign": self._opts["sign"],
            "schema": self._opts["schema"],
        }
        if self._opts["fields"] is not None:
            payload["fields"] = self._opts["fields"]  # 仅在提供 fields 时带该键（保持旧调用逐位一致）
        await _call(self._store.configure_resource, payload)  # configure_resource 为同步实现，_call 兼容
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
    # fields：资源三表「逻辑角色 → 物理字段」映射（透传给宿主 configure_resource）；
    # 缺省 None → 载荷不带该键（保持与旧调用逐位一致）
    fields = opts.get("fields")
    if fields is not None:
        _assert_fields(fields, "capability.create")
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
    # schemas：要注册进宿主的定义注入点（库不内置权威 schema）——
    # 缺省 / None / False → 不注册任何表；列表 → 逐项校验后按序注册
    schemas_opt = opts.get("schemas", [])
    if schemas_opt is None or schemas_opt is False:
        effective_schemas = []
    elif isinstance(schemas_opt, list):
        for i, defn in enumerate(schemas_opt):
            if not isinstance(defn, dict):
                raise ValueError(f"capability.create: schemas[{i}] 须为对象")
            name = defn.get("name")
            if not isinstance(name, str) or name == "":
                raise ValueError(f"capability.create: schemas[{i}].name 须为非空字符串")
        effective_schemas = copy.deepcopy(schemas_opt)
    else:
        raise ValueError("capability.create: schemas 须为数组、null 或 false")
    # 条件化门面校验：仅当有 provider 需要注册时才要求宿主门面（向后兼容旧 store）
    if len(provider_plugins) > 0:
        _assert_store(store, ("register_provider",), "capability.create")

    return _Handle(store, {
        "providers": providers, "url": url, "sign": sign, "schema": schema, "fields": fields,
        "providerPlugins": provider_plugins, "schemas": effective_schemas,
    })


# ---- adapter：接缝适配 ----


def _attr(obj, name, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _query_param(request, name):
    """请求级查询参数：兼容 Starlette request.query_params 与 dict request['query']；缺省 None。"""
    if request is None:
        return None
    qp = _attr(request, "query_params", None)
    if qp is not None and hasattr(qp, "get"):
        v = qp.get(name)
        if isinstance(v, str) and v != "":
            return v
    q = _attr(request, "query", None)
    if isinstance(q, dict):
        v = q.get(name)
        if isinstance(v, str) and v != "":
            return v
    return None


def _header(request, name):
    """请求头取值：兼容 Starlette request.headers 与 dict request['headers']；缺省 None。"""
    headers = _attr(request, "headers", None)
    if headers is None or not hasattr(headers, "get"):
        return None
    v = headers.get(name)
    return v if isinstance(v, str) and v != "" else None


async def _request_body(request):
    """上传字节体：Starlette await request.body() / dict request['body']；缺省 None。"""
    if request is None:
        return None
    if isinstance(request, dict):
        return request.get("body")
    body = getattr(request, "body", None)
    if body is None:
        return None
    out = body()
    if inspect.isawaitable(out):
        out = await out
    return out


def _pick_by_path(rec, field_path):
    """点路径取值：'images.original' → rec['images']['original']；任一段缺失 → None。"""
    if not isinstance(rec, dict):
        return None
    cur = rec
    for seg in field_path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(seg)
    return cur


def download(store, opts=None):
    _assert_store(store, ("resource_open",), "adapter.download")
    opts = {} if opts is None else opts
    if not isinstance(opts, dict):
        raise ValueError("adapter.download: opts 须为 dict")
    field = opts.get("field", "file")
    if not isinstance(field, str) or field == "":
        raise ValueError("adapter.download: field 须为非空字符串")
    order = opts.get("order")

    # 返回 store-api 既有 file_resolver 契约：(request, rec, rid) -> {body, contentType, fileName}
    async def file_resolver(request, rec, rid):
        fp = _query_param(request, "field") or field          # 请求级 field 优先，缺省回落构造期 field
        ref = _pick_by_path(rec, fp)
        if ref is None or ref == "":
            raise ValueError(f"记录缺少资源引用字段: {fp}")
        if order is None:
            opened = await _call(store.resource_open, ref)
        else:
            opened = await _call(store.resource_open, ref, order=order)
        # 元数据（fileName/mime）由宿主 resource_open 附带返回，本层不再自建 Resource 查询
        return {
            "body": _attr(opened, "bytes"),
            "contentType": _attr(opened, "mime") or "application/octet-stream",
            "fileName": _attr(opened, "fileName") or str(ref),
        }

    return file_resolver


def upload(store):
    _assert_store(store, ("resource_put",), "adapter.upload")

    # 薄透传：不改写入参、不改写出参
    async def upload_(input):
        return await _call(store.resource_put, **input)

    return upload_


def upload_resolver(store, opts=None):
    """上传接缝工厂（决策 B，与 download 对称）：(request, rec, rid) -> {"ref": sha1}。"""
    _assert_store(store, ("resource_put",), "adapter.uploadResolver")
    opts = {} if opts is None else opts
    if not isinstance(opts, dict):
        raise ValueError("adapter.uploadResolver: opts 须为 dict")
    kind = opts.get("kind", "file")
    if not isinstance(kind, str) or kind == "":
        raise ValueError("adapter.uploadResolver: kind 须为非空字符串")
    bind = opts.get("bind")
    if bind is not None and not callable(bind):
        raise ValueError("adapter.uploadResolver: bind 须为函数或 None")

    async def upload_resolver_(request, rec, rid):
        body = await _request_body(request)
        if not body:
            raise ValueError("上传字节体为空：皮未缓冲 request body 或请求体缺失")
        input_ = {"bytes": bytes(body), "kind": kind}
        file_name = _query_param(request, "fileName") or (rec or {}).get("fileName")
        mime = _query_param(request, "mime") or _header(request, "content-type")
        if file_name:
            input_["file_name"] = file_name
        if mime:
            input_["mime"] = mime
        if callable(bind):
            b = bind(request, rec, rid)
            if b is not None:
                input_["bind"] = b
        # 薄透传：字节落库仍由 store.resource_put 承担（本插件不做 IO）
        out = await _call(store.resource_put, **input_)
        ref = (out or {}).get("resourceId")
        if not ref:
            raise ValueError("resource_put 未返回 resourceId")
        return {"ref": ref}

    return upload_resolver_


capability = SimpleNamespace(schemas=schemas, create=create)
adapter = SimpleNamespace(download=download, upload=upload, upload_resolver=upload_resolver)

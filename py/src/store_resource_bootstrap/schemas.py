"""内置「可选参考」资源定义（三表）——库不再把它作为权威 schema 强制注册。

资源三表（资源目录 / 存储位置 / 业务绑定）属资源能力自身的持久化模型；
库只提供这份参考定义供开箱即用，是否注册、注册哪套，由接入方按需注入
（`capability.create(store, {"schemas": capability.schemas()})` 或自有定义）。
语义与 spec/00-protocol.md 附录 A 一致；conformance 校验本常量与之深比较全等。
注意：Resource.idPrefix 必须为空串 ""（falsy）——宿主仅当真值才生成 _id，
否则会为内容寻址资源生成随机 _id、破坏 resourceId = sha1 约定。
"""
from __future__ import annotations

RESOURCE_SCHEMAS: list[dict] = [
    {
        "name": "Resource", "collection": "resources", "idPrefix": "", "timestamps": True,
        # read 未配置（None）= 不限制，走宿主 unconfigured_policy 缺省 open；
        # write: [] 为显式拒写（资源行只由 internal 上传流程写入），语义见 spec 附录 A。
        "read": None, "write": [],
        "fields": {
            "_id":      {"type": "string"},
            "sha1":     {"type": "string"},
            "fileName": {"type": "string"},
            "mime":     {"type": "string"},
            "size":     {"type": "int"},
            "kind":     {"type": "string"},
        },
        "relations": {},
        "indexes": [
            {"keys": {"sha1": 1}, "options": {"unique": True}},
        ],
    },
    {
        "name": "ResourceLocation", "collection": "resource_locations", "idPrefix": "rl", "timestamps": True,
        # 同 Resource：读不限制、写显式拒绝（位置行由 internal 存储流程维护）。
        "read": None, "write": [],
        "fields": {
            "_id":        {"type": "string"},
            "resourceId": {"type": "string"},
            "backend":    {"type": "string"},
            "key":        {"type": "string"},
            "status":     {"type": "string"},
            "priority":   {"type": "int"},
        },
        "relations": {
            # 关系读不限制（未配置 = 走 unconfigured_policy），与主表读姿态一致。
            "resource": {"model": "Resource", "type": "one", "localField": "resourceId", "foreignField": "_id", "read": None},
        },
        "indexes": [
            {"keys": {"resourceId": 1, "backend": 1}, "options": {"unique": True}},
        ],
    },
    {
        "name": "ResourceBinding", "collection": "resource_bindings", "idPrefix": "rb", "timestamps": True,
        # 同 Resource：读不限制、写显式拒绝（绑定行由 internal 业务流程维护）。
        "read": None, "write": [],
        "fields": {
            "_id":           {"type": "string"},
            "resourceId":    {"type": "string"},
            "businessTable": {"type": "string"},
            "businessId":    {"type": "string"},
            "userId":        {"type": "string"},
        },
        "relations": {
            # 关系读不限制（未配置 = 走 unconfigured_policy），与主表读姿态一致。
            "resource": {"model": "Resource", "type": "one", "localField": "resourceId", "foreignField": "_id", "read": None},
        },
        "indexes": [
            {"keys": {"resourceId": 1, "businessTable": 1, "businessId": 1}, "options": {"unique": True}},
        ],
    },
]

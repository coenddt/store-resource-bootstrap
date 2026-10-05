"""MinIO provider 预设：自建网关须 path-style。"""
from . import s3_compat

PRESET = {"kind": "minio", "forcePathStyle": True}


def create(options=None, sdk=None):
    merged = {**PRESET, **(options or {}), "kind": "minio"}
    return s3_compat.create(merged, sdk)

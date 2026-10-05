"""OSS provider 预设：仅 virtual-hosted；boto3 须用 V2 签名。"""
from . import s3_compat

PRESET = {"kind": "oss", "forcePathStyle": False, "signatureVersion": "s3"}


def create(options=None, sdk=None):
    merged = {**PRESET, **(options or {}), "kind": "oss"}
    return s3_compat.create(merged, sdk)

"""可选 provider 参考模块命名空间（oss / minio）。"""
from . import minio as minio
from . import oss as oss

__all__ = ["oss", "minio"]

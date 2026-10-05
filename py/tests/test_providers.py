"""可选 provider 参考模块单测。"""
import sys
from types import SimpleNamespace

from store_resource_bootstrap import providers


class _FakeConfig:
    def __init__(self, **kw):
        self.kw = kw


def _capture_sdk(captured):
    def fake_client(service, **kw):
        captured["client_kw"] = kw
        return SimpleNamespace()
    return {"client": fake_client, "config": _FakeConfig}


def test_namespace_exports():
    assert callable(providers.oss.create)
    assert callable(providers.minio.create)


def test_presets():
    assert providers.oss.PRESET == {"kind": "oss", "forcePathStyle": False, "signatureVersion": "s3"}
    assert providers.minio.PRESET == {"kind": "minio", "forcePathStyle": True}


def test_oss_virtual_host_and_v2_signature():
    captured = {}
    providers.oss.create({"bucket": "b", "endpoint": "https://oss.example.com"}, sdk=_capture_sdk(captured))
    assert captured["client_kw"]["config"].kw == {
        "s3": {"addressing_style": "virtual"}, "signature_version": "s3",
    }


def test_minio_path_style():
    captured = {}
    providers.minio.create({"bucket": "b", "endpoint": "http://minio:9000"}, sdk=_capture_sdk(captured))
    assert captured["client_kw"]["config"].kw == {"s3": {"addressing_style": "path"}}


def test_sdk_not_eagerly_imported():
    assert "boto3" not in sys.modules

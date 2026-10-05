"""S3 兼容 provider 参考实现（OSS / MinIO / AWS 共用）；SDK 懒加载。"""
import asyncio


def create(options=None, sdk=None):
    options = options or {}
    if sdk is None:
        import boto3  # 懒加载：未安装 SDK 时仅本模块 create() 报错
        from botocore.config import Config
        sdk = {"client": boto3.client, "config": Config}

    bucket = options.get("bucket")
    if not bucket:
        raise ValueError("s3-compat provider 需要 options.bucket")

    client = options.get("client")
    if client is None:
        endpoint = options.get("endpoint")
        force_path = options.get("forcePathStyle")
        if force_path is None:
            force_path = bool(endpoint)
        addressing = "path" if force_path else "virtual"
        creds = options.get("credentials") or {}
        client = sdk["client"](
            "s3",
            region_name=options.get("region") or "us-east-1",
            endpoint_url=endpoint,
            aws_access_key_id=creds.get("accessKeyId"),
            aws_secret_access_key=creds.get("secretAccessKey"),
            config=_config(sdk["config"], addressing, options.get("signatureVersion")),
        )

    prefix = options.get("prefix")

    def key_of(key):
        if prefix:
            return f"{str(prefix).rstrip('/')}/{key}"
        return key

    def _put(key, data, opts):
        client.put_object(
            Bucket=bucket,
            Key=key_of(key),
            Body=data,
            ContentType=(opts or {}).get("mime") or "application/octet-stream",
        )

    def _get(key):
        r = client.get_object(Bucket=bucket, Key=key_of(key))
        return r["Body"].read()

    def _remove(key):
        client.delete_object(Bucket=bucket, Key=key_of(key))

    def _exists(key):
        try:
            client.head_object(Bucket=bucket, Key=key_of(key))
            return True
        except Exception as e:
            response = getattr(e, "response", {}) or {}
            status = (response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
            err_code = (response.get("Error") or {}).get("Code")
            if status == 404 or err_code in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    async def put(key, data, opts=None):
        await asyncio.to_thread(_put, key, data, opts)

    async def get(key, opts=None):
        return await asyncio.to_thread(_get, key)

    async def remove(key, opts=None):
        await asyncio.to_thread(_remove, key)

    async def exists(key, opts=None):
        return await asyncio.to_thread(_exists, key)

    return {"kind": options.get("kind", "s3"), "put": put, "get": get, "remove": remove, "exists": exists}


def _config(config_cls, addressing, signature_version=None):
    kwargs = {"s3": {"addressing_style": addressing}}
    if signature_version:
        kwargs["signature_version"] = signature_version
    return config_cls(**kwargs)

'use strict';

/**
 * S3 兼容 provider 参考实现（OSS / MinIO / AWS 共用）。
 * SDK 懒加载：`deps` 未注入时才 require('@aws-sdk/client-s3')——未安装 SDK 时
 * 仅本模块 create() 报错，插件装载 / capability / adapter / 测试均不受影响。
 */
function create(options = {}, deps) {
  const {
    S3Client, PutObjectCommand, GetObjectCommand, DeleteObjectCommand, HeadObjectCommand,
  } = deps || require('@aws-sdk/client-s3');
  const bucket = options.bucket;
  if (!bucket) throw new Error('s3-compat provider 需要 options.bucket');
  const client = options.client || new S3Client({
    region: options.region || 'us-east-1',
    endpoint: options.endpoint,
    // 显式优先：MinIO / 自建网关需 path-style，OSS 须 virtual-hosted（预设显式 false 覆盖 endpoint 推断）
    forcePathStyle: options.forcePathStyle ?? !!options.endpoint,
    credentials: options.credentials,
  });
  const keyOf = (key) => (options.prefix ? `${String(options.prefix).replace(/\/$/, '')}/${key}` : key);
  return {
    kind: options.kind || 's3',
    async put(key, bytes, opts = {}) {
      await client.send(new PutObjectCommand({
        Bucket: bucket, Key: keyOf(key), Body: bytes,
        ContentType: (opts && opts.mime) || 'application/octet-stream',
      }));
    },
    async get(key) {
      const r = await client.send(new GetObjectCommand({ Bucket: bucket, Key: keyOf(key) }));
      return Buffer.from(await r.Body.transformToByteArray());
    },
    async remove(key) {
      await client.send(new DeleteObjectCommand({ Bucket: bucket, Key: keyOf(key) }));
    },
    async exists(key) {
      try { await client.send(new HeadObjectCommand({ Bucket: bucket, Key: keyOf(key) })); return true; }
      catch (e) {
        const code = e && e.$metadata && e.$metadata.httpStatusCode;
        if (code === 404 || (e && (e.name === 'NotFound' || e.name === 'NoSuchKey'))) return false;
        throw e; // 非缺省一律抛出（禁掩盖）
      }
    },
  };
}

module.exports = { create };

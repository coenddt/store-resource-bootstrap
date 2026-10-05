'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const providers = require('../src/providers');

test('P1 命名空间导出 oss / minio', () => {
  assert.equal(typeof providers.oss.create, 'function');
  assert.equal(typeof providers.minio.create, 'function');
});

test('P2 preset 值', () => {
  assert.deepEqual(providers.oss.preset, { kind: 'oss', forcePathStyle: false });
  assert.deepEqual(providers.minio.preset, { kind: 'minio', forcePathStyle: true });
});

test('P3 注入 fake SDK 断言 forcePathStyle 生效', () => {
  const captured = {};
  const fakeSdk = {
    S3Client: class { constructor(cfg) { captured.client = cfg; } send() {} },
    PutObjectCommand: class {}, GetObjectCommand: class {},
    DeleteObjectCommand: class {}, HeadObjectCommand: class {},
  };

  providers.oss.create({ bucket: 'b', endpoint: 'https://oss-cn-hangzhou.aliyuncs.com' }, fakeSdk);
  assert.equal(captured.client.forcePathStyle, false);   // 预设显式 false，覆盖 endpoint 推断
  assert.equal(captured.client.endpoint, 'https://oss-cn-hangzhou.aliyuncs.com');

  providers.minio.create({ bucket: 'b', endpoint: 'http://minio:9000' }, fakeSdk);
  assert.equal(captured.client.forcePathStyle, true);
});

test('P4 未安装 SDK 亦可装载（require.cache 无 @aws-sdk/client-s3）', () => {
  const loaded = Object.keys(require.cache).some((k) => k.includes('@aws-sdk/client-s3'));
  assert.equal(loaded, false);
});

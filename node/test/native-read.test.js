'use strict';

/**
 * 真实宿主语义验证（opt-in）：参考三表经 capability.start() 注册后，
 * 普通角色可读（read: null = 未配置 → unconfiguredPolicy 缺省 open）。
 *
 * 需外部环境：STORE_NATIVE=1 + MongoDB + 可解析 nodejs-store
 * （NODE_PATH 指向 monorepo 根与 nodejs-store/node_modules）。
 * 未设 STORE_NATIVE 时整组跳过（默认 npm test 仍走 mock 单测）。
 */

const test = require('node:test');
const assert = require('node:assert/strict');

const { capability } = require('../src');

const ENABLED = process.env.STORE_NATIVE === '1';
const MONGO_URI = process.env.MONGO_URI || 'mongodb://127.0.0.1:27017';

test('参考三表 bootstrap 后对普通角色可读（真实 core）', { skip: !ENABLED, timeout: 60000 }, async () => {
  const { MongoClient } = require('mongodb');
  const host = require('nodejs-store');
  const client = new MongoClient(MONGO_URI);
  await client.connect();
  try {
    const db = client.db('resource_native_read');
    await db.dropDatabase();
    await host.init(db);

    const handle = capability.create(host.store, {
      // 最小合法 provider 配置：只为通过宿主 configureResource 形状校验（本用例不落文件）
      providers: [{ kind: 'local', options: { root: require('node:path').join(require('node:os').tmpdir(), 'resource-native-read') }, priority: 0 }],
      schemas: capability.schemas(),
    });
    const started = await handle.start();
    assert.deepEqual(started.registered, ['Resource', 'ResourceLocation', 'ResourceBinding']);

    // 普通角色（非 internal、非豁免）：read: null ⇒ 不限制
    host.store.setContext({ userId: 'u1', role: 'member' });
    assert.deepEqual(await host.store.query('Resource', '{ _id sha1 }', {}), []);
    assert.deepEqual(await host.store.query('ResourceLocation', '{ _id key }', {}), []);
    assert.deepEqual(await host.store.query('ResourceBinding', '{ _id resourceId }', {}), []);

    // 对照：显式空名单仍是拒读（防回退为「空数组 = 不限制」）
    host.store.register({
      name: 'P_Empty', collection: 'p_empty', read: [], write: [],
      fields: { _id: { type: 'string' } }, relations: {}, indexes: [],
    });
    await assert.rejects(() => host.store.query('P_Empty', '{ _id }', {}), /无访问权限/);
  } finally {
    await client.close();
  }
});

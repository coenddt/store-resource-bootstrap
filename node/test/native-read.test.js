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

test('write: [] 拒写 + closed 姿态下 read: null 整表不可见（真实 core）', { skip: !ENABLED, timeout: 60000 }, async () => {
  const { MongoClient } = require('mongodb');
  const host = require('nodejs-store');
  const client = new MongoClient(MONGO_URI);
  await client.connect();
  try {
    const db = client.db('resource_native_scope');
    await db.dropDatabase();
    await host.init(db);
    const handle = capability.create(host.store, {
      providers: [{ kind: 'local', options: { root: require('node:path').join(require('node:os').tmpdir(), 'resource-native-scope') }, priority: 0 }],
      schemas: capability.schemas(),
    });
    await handle.start();

    host.store.setContext({ userId: 'u1', role: 'member' });
    // 参考 schema write: [] = 显式拒写
    await assert.rejects(
      () => host.store.insert('Resource', { _id: 'res1', sha1: 'abc' }),
      /无写入权限/,
    );
    // closed 姿态：三表 read: null 对非内部上下文整表不可见（fail-secure）
    host.store.setUnconfiguredPolicy('closed');
    for (const name of ['Resource', 'ResourceLocation', 'ResourceBinding']) {
      await assert.rejects(() => host.store.query(name, '{ _id }', {}), /无访问权限/);
    }
    // internal 直通（HEAD 宿主已禁止 setContext 注入 internal，内部调用必须走 runAsInternal）
    const internalRows = await host.store.runAsInternal(() => host.store.query('Resource', '{ _id }', {}));
    assert.deepEqual(internalRows, []);
  } finally {
    host.store.setContext(null);
    host.store.setUnconfiguredPolicy('open');
    await client.close();
  }
});

test('start() 中途 schema 注册失败 ⇒ 已注册表残留（真实门面，非原子）', { skip: !ENABLED, timeout: 60000 }, async () => {
  const { MongoClient } = require('mongodb');
  const host = require('nodejs-store');
  const client = new MongoClient(MONGO_URI);
  await client.connect();
  try {
    const db = client.db('resource_native_partial');
    await db.dropDatabase();
    await host.init(db);
    const handle = capability.create(host.store, {
      providers: [{ kind: 'local', options: { root: require('node:path').join(require('node:os').tmpdir(), 'resource-native-partial') }, priority: 0 }],
      schemas: [
        { name: 'PartialA', collection: 'partial_a', read: null, write: [], fields: { _id: { type: 'string' } }, relations: {}, indexes: [] },
        { name: 'PartialB', collection: 'partial_b', read: null, write: [], fields: { _id: { type: 'string' } }, relations: {}, indexes: [] },
      ],
    });
    const original = host.store.register.bind(host.store);
    let calls = 0;
    host.store.register = (defn) => {
      calls += 1;
      if (calls === 2) throw new Error('注入失败：第二张表注册失败');
      return original(defn);
    };
    await assert.rejects(() => handle.start(), /注入失败/);
    assert.equal(host.store.has('PartialA'), true);
    assert.equal(host.store.has('PartialB'), false);
  } finally {
    await client.close();
  }
});

test('configureResource 失败 ⇒ schema 零注册（真实 core，零副作用）', { skip: !ENABLED, timeout: 60000 }, async () => {
  const { MongoClient } = require('mongodb');
  const host = require('nodejs-store');
  const client = new MongoClient(MONGO_URI);
  await client.connect();
  try {
    const db = client.db('resource_native_cfg_fail');
    await db.dropDatabase();
    await host.init(db);
    const handle = capability.create(host.store, {
      // 未知 provider kind：宿主 configureResource 应在建池时拒绝（本用例取真实失败路径）
      providers: [{ kind: 'bogus-kind', options: {} }],
      schemas: [
        { name: 'CfgFailA', collection: 'cfg_fail_a', read: null, write: [], fields: { _id: { type: 'string' } }, relations: {}, indexes: [] },
      ],
    });
    let regs = 0;
    const original = host.store.register.bind(host.store);
    host.store.register = (defn) => { regs += 1; return original(defn); };
    await assert.rejects(() => handle.start());
    assert.equal(regs, 0, 'configureResource 失败后不得注册任何 schema');
    assert.equal(host.store.has('CfgFailA'), false);
  } finally {
    await client.close();
  }
});

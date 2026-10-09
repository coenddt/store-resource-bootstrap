'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { capability } = require('../src/index.js');
const { mockStore } = require('./mock-store.js');

const OK_OPTS = { providers: [{ kind: 'local', options: { root: '/data' }, priority: 0 }] };

test('C1 schemas() 表数 / 表名', () => {
  const list = capability.schemas();
  assert.equal(list.length, 3);
  assert.deepEqual(list.map((d) => d.name), ['Resource', 'ResourceLocation', 'ResourceBinding']);
});

test('C2 schemas() 关键字段', () => {
  const [res, loc, bind] = capability.schemas();
  assert.equal(res.idPrefix, '');
  assert.equal(res.collection, 'resources');
  assert.deepEqual(res.indexes, [{ keys: { sha1: 1 }, options: { unique: true } }]);
  assert.equal(loc.idPrefix, 'rl');
  assert.deepEqual(loc.indexes, [{ keys: { resourceId: 1, backend: 1 }, options: { unique: true } }]);
  assert.equal(bind.idPrefix, 'rb');
  assert.deepEqual(bind.indexes, [
    { keys: { resourceId: 1, businessTable: 1, businessId: 1 }, options: { unique: true } },
  ]);
});

test('C3 schemas() 深拷贝', () => {
  const first = capability.schemas();
  first[0].fields._id.type = 'int';
  assert.equal(capability.schemas()[0].fields._id.type, 'string');
});

test('C4 store 缺门面', () => {
  assert.throws(() => capability.create({}, OK_OPTS), /register/);
});

test('C5 providers 缺失/空', () => {
  const store = mockStore();
  assert.throws(() => capability.create(store, {}), /providers/);
  assert.throws(() => capability.create(store, { providers: [] }), /providers/);
});

test('C6 providers 项非法', () => {
  const store = mockStore();
  assert.throws(() => capability.create(store, { providers: [{ kind: '' }] }), /kind/);
  assert.throws(() => capability.create(store, { providers: [{ kind: 'local', priority: 1.5 }] }), /priority/);
  assert.throws(() => capability.create(store, { providers: [{ kind: 'local', options: 1 }] }), /options/);
});

test('C7 未知配置键', () => {
  const store = mockStore();
  assert.throws(() => capability.create(store, { providers: [{ kind: 'local' }], foo: 1 }), /foo/);
});

test('C8 url / sign 非法', () => {
  const store = mockStore();
  assert.throws(() => capability.create(store, { providers: [{ kind: 'local' }], url: 1 }), /url/);
  assert.throws(() => capability.create(store, { providers: [{ kind: 'local' }], sign: 'x' }), /sign/);
});

test('C9 start() 缺省不注册任何表（schema 交业务/宿主）', async () => {
  const store = mockStore();
  const out = await capability.create(store, OK_OPTS).start();
  assert.deepEqual(out, { registered: [], skipped: [], providerRegistered: [] });
  assert.deepEqual(store.calls.map((c) => c[0]), ['configureResource']);
});

test('C9b start() 注入 schemas 时注册三表', async () => {
  const store = mockStore();
  const out = await capability.create(store, { ...OK_OPTS, schemas: capability.schemas() }).start();
  assert.deepEqual(out, {
    registered: ['Resource', 'ResourceLocation', 'ResourceBinding'],
    skipped: [],
    providerRegistered: [],
  });
  assert.deepEqual(store.calls.map((c) => c[0]), ['register', 'register', 'register', 'configureResource']);
  assert.deepEqual(store.calls.slice(0, 3).map((c) => c[1]), ['Resource', 'ResourceLocation', 'ResourceBinding']);
});

test('C10 configureResource 入参（显式）', async () => {
  const store = mockStore();
  const sign = () => {};
  const opts = {
    providers: [{ kind: 'local' }],
    url: { base: 'https://cdn' },
    sign,
    schema: { resource: 'R' },
  };
  await capability.create(store, opts).start();
  const cfg = store.calls.find((c) => c[0] === 'configureResource')[1];
  assert.equal(cfg.providers, opts.providers);
  assert.deepEqual(cfg.url, { base: 'https://cdn' });
  assert.equal(cfg.sign, sign);
  assert.deepEqual(cfg.schema, { resource: 'R' });
});

test('C10b configureResource 入参（缺省）', async () => {
  const store = mockStore();
  await capability.create(store, { providers: [{ kind: 'local' }] }).start();
  const cfg = store.calls.find((c) => c[0] === 'configureResource')[1];
  assert.deepEqual(cfg.url, {});
  assert.equal(cfg.sign, null);
  assert.deepEqual(cfg.schema, { resource: 'Resource', location: 'ResourceLocation', binding: 'ResourceBinding' });
  assert.equal('fields' in cfg, false);   // 未提供 fields 时载荷不带该键
});

test('C19 fields 透传（提供时逐位一致）', async () => {
  const store = mockStore();
  const fields = {
    resource: { sha1: 'contentHash', size: null },
    location: { backend: 'store', status: null },
    binding: { businessTable: 'entity', userId: null },
  };
  await capability.create(store, { providers: [{ kind: 'local' }], fields }).start();
  const cfg = store.calls.find((c) => c[0] === 'configureResource')[1];
  assert.deepEqual(cfg.fields, fields);
});

test('C20 fields 非法形状抛错且零门面调用', () => {
  const base = { providers: [{ kind: 'local' }] };
  const cases = [
    { fields: 1, hit: /fields/ },
    { fields: { bogus: {} }, hit: /fields/ },
    { fields: { resource: 1 }, hit: /fields/ },
    { fields: { resource: { bogus: 'x' } }, hit: /fields/ },
    { fields: { resource: { sha1: null } }, hit: /sha1/ },
    { fields: { location: { backend: '' } }, hit: /backend/ },
    { fields: { binding: { userId: 1 } }, hit: /userId/ },
  ];
  for (const c of cases) {
    const store = mockStore();
    assert.throws(() => capability.create(store, { ...base, fields: c.fields }), c.hit);
    assert.equal(store.calls.length, 0);
  }
});

test('C11 start() 幂等', async () => {
  const store = mockStore();
  const handle = capability.create(store, { ...OK_OPTS, schemas: capability.schemas() });
  await handle.start();
  const regCount1 = store.calls.filter((c) => c[0] === 'register').length;
  const out2 = await handle.start();
  assert.deepEqual(out2, {
    registered: [],
    skipped: ['Resource', 'ResourceLocation', 'ResourceBinding'],
    providerRegistered: [],
  });
  assert.equal(store.calls.filter((c) => c[0] === 'register').length, regCount1);
  assert.equal(store.calls.filter((c) => c[0] === 'configureResource').length, 2);
});

test('C12 reload() ≡ start', async () => {
  const store = mockStore();
  const handle = capability.create(store, { ...OK_OPTS, schemas: capability.schemas() });
  await handle.start();
  const regCount1 = store.calls.filter((c) => c[0] === 'register').length;
  await handle.reload();
  assert.equal(store.calls.filter((c) => c[0] === 'register').length, regCount1);
  assert.equal(store.calls.filter((c) => c[0] === 'configureResource').length, 2);
});

test('C13 provider kind 不预检', () => {
  const store = mockStore();
  assert.doesNotThrow(() => capability.create(store, { providers: [{ kind: 'unknown-kind' }] }));
});

test('C14 providerPlugins 前置注册', async () => {
  const store = mockStore();
  const fn = (o) => ({ kind: 'oss', o });
  const out = await capability.create(store, {
    providers: [{ kind: 'local' }],
    providerPlugins: [{ kind: 'oss', create: fn }],
    schemas: capability.schemas(),
  }).start();
  assert.deepEqual(store.calls.map((c) => c[0]), ['registerProvider', 'register', 'register', 'register', 'configureResource']);
  assert.equal(store.calls[0][1], 'oss');
  assert.equal(store.calls[0][2].create, fn);
  assert.deepEqual(out.providerRegistered, ['oss']);
});

test('C15 providerPlugins 非空但缺门面', () => {
  const store = mockStore();
  delete store.registerProvider;
  assert.throws(
    () => capability.create(store, {
      providers: [{ kind: 'local' }],
      providerPlugins: [{ kind: 'oss', create: () => ({}) }],
    }),
    /registerProvider/,
  );
});

test('C16 未传 / 空数组不要求 registerProvider 门面', () => {
  const store = mockStore();
  delete store.registerProvider;
  assert.doesNotThrow(() => capability.create(store, { providers: [{ kind: 'local' }] }));
  assert.doesNotThrow(() => capability.create(store, { providers: [{ kind: 'local' }], providerPlugins: [] }));
});

test('C17 schemas 非法配置', () => {
  const store = mockStore();
  assert.throws(() => capability.create(store, { providers: [{ kind: 'local' }], schemas: 1 }), /schemas/);
  assert.throws(() => capability.create(store, { providers: [{ kind: 'local' }], schemas: [1] }), /schemas/);
  assert.throws(() => capability.create(store, { providers: [{ kind: 'local' }], schemas: [{}] }), /schemas/);
});

test('C18 schemas 注入自定义定义只注册该定义', async () => {
  const store = mockStore();
  const defn = {
    name: 'BizAsset', collection: 'biz_assets', idPrefix: 'ba', timestamps: true,
    read: [], write: [], fields: { _id: { type: 'string' } }, relations: {}, indexes: [],
  };
  const out = await capability.create(store, { providers: [{ kind: 'local' }], schemas: [defn] }).start();
  assert.deepEqual(out.registered, ['BizAsset']);
  assert.deepEqual(store.calls.map((c) => c[0]), ['register', 'configureResource']);
  assert.equal(store.calls[0][1], 'BizAsset');
});

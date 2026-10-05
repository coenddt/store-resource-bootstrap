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

test('C9 start() 首次', async () => {
  const store = mockStore();
  const out = await capability.create(store, OK_OPTS).start();
  assert.deepEqual(out, {
    registered: ['Resource', 'ResourceLocation', 'ResourceBinding'],
    skipped: [],
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
});

test('C11 start() 幂等', async () => {
  const store = mockStore();
  const handle = capability.create(store, OK_OPTS);
  await handle.start();
  const regCount1 = store.calls.filter((c) => c[0] === 'register').length;
  const out2 = await handle.start();
  assert.deepEqual(out2, {
    registered: [],
    skipped: ['Resource', 'ResourceLocation', 'ResourceBinding'],
  });
  assert.equal(store.calls.filter((c) => c[0] === 'register').length, regCount1);
  assert.equal(store.calls.filter((c) => c[0] === 'configureResource').length, 2);
});

test('C12 reload() ≡ start', async () => {
  const store = mockStore();
  const handle = capability.create(store, OK_OPTS);
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

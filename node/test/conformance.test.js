'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const cases = require('../../conformance/cases.json');
const { capability, adapter } = require('../src');
const { mockStore } = require('./mock-store');

test('conformance · schemas 三表与 canonical 深比较全等', () => {
  const got = capability.schemas();
  assert.deepEqual(got, cases.schemas.canonical);
  assert.deepEqual(got.map((d) => d.name), cases.schemas.names);
  for (const d of got) {
    assert.equal(d.collection, cases.schemas.collections[d.name]);
    assert.equal(d.idPrefix, cases.schemas.id_prefixes[d.name]);
  }
});

test('conformance · schemas 深拷贝（改写不回写内部）', () => {
  const a = capability.schemas();
  a[0].fields._id.type = 'number';
  assert.equal(capability.schemas()[0].fields._id.type, 'string');
});

for (const key of ['fresh', 'idempotent', 'defaults', 'schemas_disabled', 'custom_schemas', 'fields_passthrough']) {
  test(`conformance · capability.${key} 调用序列与返回逐位一致`, async () => {
    const entry = cases.capability[key];
    const store = mockStore(entry.seed);
    // schemas_ref: 'canonical' → 用内置可选参考定义作为 opts.schemas 注入（缺省不注册）
    const opts = entry.schemas_ref === 'canonical'
      ? { ...entry.opts, schemas: cases.schemas.canonical }
      : entry.opts;
    const handle = capability.create(store, opts);
    const out = await handle.start();
    assert.deepEqual(store.calls, entry.expected_calls);
    assert.deepEqual(out, entry.expected_return);
  });
}

test('conformance · capability.provider_plugins 前置注册与三元返回', async () => {
  const entry = cases.capability.provider_plugins;
  const store = mockStore(entry.seed);
  const creates = entry.opts.providerPlugins.map((_, i) => (options) => ({ kind: 'stub', i, options }));
  const opts = {
    ...entry.opts,
    providerPlugins: entry.opts.providerPlugins.map((spec, i) => ({ kind: spec.kind, create: creates[i] })),
  };
  if (entry.schemas_ref === 'canonical') opts.schemas = cases.schemas.canonical;
  const out = await capability.create(store, opts).start();

  // 每项 kind 前置注册，且 create 引用一致
  const regCalls = store.calls.filter((c) => c[0] === 'registerProvider');
  assert.deepEqual(out.providerRegistered, entry.expected_registered_kinds);
  assert.equal(regCalls.length, entry.expected_registered_kinds.length);
  regCalls.forEach((c, i) => {
    assert.equal(c[1], entry.expected_registered_kinds[i]);
    assert.equal(c[2].create, creates[i]);
  });

  // provider 注册先于 configureResource
  const names = store.calls.map((c) => c[0]);
  assert.ok(names.lastIndexOf('registerProvider') < names.indexOf('configureResource'));

  // 尾部调用（configureResource 入参）与剩余返回逐位一致
  assert.deepEqual(store.calls.slice(-entry.expected_tail_calls.length), entry.expected_tail_calls);
  for (const [k, v] of Object.entries(entry.expected_return_rest)) {
    assert.deepEqual(out[k], v);
  }
});

test('conformance · capability.invalid 抛错且零门面调用', () => {
  for (const c of cases.capability.invalid) {
    const store = mockStore();
    assert.throws(
      () => capability.create(store, c.opts),
      (e) => {
        assert.ok(e instanceof Error, `${c.name} 应抛 Error`);
        assert.ok(e.message.includes(c.error_contains), `${c.name} 消息应含 ${c.error_contains}`);
        return true;
      },
    );
    assert.equal(store.calls.length, c.expected_call_count, `${c.name} 应零门面调用`);
  }
});

test('conformance · adapter.download 正常路径', async () => {
  const c = cases.adapter.download;
  const store = mockStore();
  const resolve = adapter.download(store, c.opts);
  const out = await resolve({}, c.record, 'id1');
  assert.equal(store.calls.length, 1);            // 仅一次 resourceOpen（不再自建 Resource 查询）
  assert.deepEqual(store.calls[0], c.expected_open_call);
  assert.equal(out.contentType, c.expected_result.contentType);
  assert.equal(out.fileName, c.expected_result.fileName);
  assert.equal(out.body.toString(), c.expected_result.body_text);
});

test('conformance · adapter.download 自定义 field / order', async () => {
  const f = cases.adapter.download_field;
  const s1 = mockStore();
  await adapter.download(s1, f.opts)({}, f.record, 'id1');
  assert.deepEqual(s1.calls[0], f.expected_open_call);

  const o = cases.adapter.download_order;
  const s2 = mockStore();
  await adapter.download(s2, o.opts)({}, o.record, 'id1');
  assert.deepEqual(s2.calls[0], o.expected_open_call);
});

test('conformance · adapter.download 缺引用抛错且零资源调用', async () => {
  for (const c of cases.adapter.missing_ref) {
    const store = mockStore();
    const resolve = adapter.download(store, {});
    await assert.rejects(() => resolve({}, c.record, 'id1'), (e) => {
      assert.ok(e instanceof Error, `${c.name} 应抛 Error`);
      assert.ok(e.message.includes(c.error_contains), `${c.name} 消息应含 ${c.error_contains}`);
      return true;
    });
    assert.equal(store.calls.length, 0, `${c.name} 应零资源调用`);
  }
});

test('conformance · adapter.download mime / fileName 缺省兜底', async () => {
  const m = cases.adapter.mime_fallback;
  const s1 = mockStore();
  s1.resourceOpen = async (id, opts) => ({ bytes: Buffer.from('hello'), ...m.open });
  const o1 = await adapter.download(s1, {})({}, { file: 'ref1' }, 'id1');
  assert.equal(o1.contentType, m.expected.contentType);
  assert.equal(o1.fileName, m.expected.fileName);

  const f = cases.adapter.filename_fallback;
  const s2 = mockStore();
  s2.resourceOpen = async (id, opts) => ({ bytes: Buffer.from('hello'), ...f.open });
  const o2 = await adapter.download(s2, {})({}, { file: 'ref1' }, 'id1');
  assert.equal(o2.contentType, f.expected.contentType);
  assert.equal(o2.fileName, f.expected.fileName);
});

test('conformance · adapter.upload 薄透传', async () => {
  const { input } = cases.adapter.upload;
  const store = mockStore();
  const ret = await adapter.upload(store)(input);
  assert.deepEqual(store.calls[0], ['resourcePut', input]);
  assert.deepEqual(ret, { resourceId: 'sha1', sha1: 'sha1', locations: [] });
});

test('conformance · adapter.download 点路径 / 请求级 field', async () => {
  const d = cases.adapter.download_dot_path;
  const s1 = mockStore();
  await adapter.download(s1, d.opts)({}, d.record, 'id1');
  assert.deepEqual(s1.calls[0], d.expected_open_call);

  const r = cases.adapter.download_request_field;
  const s2 = mockStore();
  await adapter.download(s2, r.opts)({ query: { ...r.request_query } }, r.record, 'id1');
  assert.deepEqual(s2.calls[0], r.expected_open_call);
});

test('conformance · adapter.uploadResolver 落库且返回 ref', async () => {
  const c = cases.adapter.upload_resolver;
  const store = mockStore();
  const req = {
    body: Buffer.from(c.request.body_bytes),
    query: { ...c.request.query },
    headers: { ...c.request.headers },
  };
  const out = await adapter.uploadResolver(store, c.opts)(req, c.record, c.record._id);
  const put = store.calls.find((x) => x[0] === 'resourcePut')[1];
  assert.deepEqual(put.bytes, Buffer.from(c.expected_put.node.bytes));
  assert.equal(put.kind, c.expected_put.node.kind);
  assert.equal(put.fileName, c.expected_put.node.fileName);
  assert.equal(put.mime, c.expected_put.node.mime);
  assert.deepEqual(out, { ref: c.expected_ref });
});

test('conformance · 机检：src 无禁用字样', () => {
  const dir = path.join(__dirname, '..', 'src');
  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.js'));
  const blocked = [
    ...cases.machine_checks.forbidden_literals,
    ...cases.machine_checks.forbidden_host_refs,
    ...cases.machine_checks.forbidden_calls,
  ];
  let hits = 0;
  for (const f of files) {
    const text = fs.readFileSync(path.join(dir, f), 'utf8');
    for (const token of blocked) if (text.includes(token)) { hits++; }
  }
  assert.equal(hits, 0, `src 命中禁用字样 ${hits} 处`);
});

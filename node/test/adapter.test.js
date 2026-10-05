'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { adapter } = require('../src/index.js');
const { mockStore } = require('./mock-store.js');

const PROJECTION = 'Resource($condition: @c0) { _id, fileName, mime }';

test('D1 download 正常路径', async () => {
  const store = mockStore();
  const out = await adapter.download(store)({}, { file: 'ref1' }, 'id1');
  assert.equal(Buffer.isBuffer(out.body), true);
  assert.equal(out.contentType, 'text/plain');
  assert.equal(out.fileName, 'a.txt');
  assert.deepEqual(store.calls.find((c) => c[0] === 'resourceOpen'), ['resourceOpen', 'ref1', {}]);
  assert.deepEqual(store.calls.find((c) => c[0] === 'queryOne'), ['queryOne', PROJECTION, { c0: { _id: 'ref1' } }]);
});

test('D2 自定义 field', async () => {
  const store = mockStore();
  const out = await adapter.download(store, { field: 'coverId' })({}, { coverId: 'c1' }, 'id');
  assert.equal(store.calls.find((c) => c[0] === 'resourceOpen')[1], 'c1');
  assert.equal(out.fileName, 'a.txt');
});

test('D3 order 透传', async () => {
  const store = mockStore();
  await adapter.download(store, { order: ['local'] })({}, { file: 'ref1' }, 'id');
  assert.deepEqual(store.calls.find((c) => c[0] === 'resourceOpen'), ['resourceOpen', 'ref1', { order: ['local'] }]);
});

test('D4 缺引用字段', async () => {
  const store = mockStore();
  await assert.rejects(() => adapter.download(store)({}, {}, 'id'), /file/);
  assert.equal(store.calls.some((c) => c[0] === 'resourceOpen'), false);
});

test('D5 引用为空串', async () => {
  const store = mockStore();
  await assert.rejects(() => adapter.download(store)({}, { file: '' }, 'id'), /file/);
});

test('D6 mime 缺失兜底', async () => {
  const store = mockStore();
  store.queryOne = async () => ({ _id: 'ref1', mime: null, fileName: 'x' });
  const out = await adapter.download(store)({}, { file: 'ref1' }, 'id');
  assert.equal(out.contentType, 'application/octet-stream');
});

test('D7 fileName 缺失兜底', async () => {
  const store = mockStore();
  store.queryOne = async () => ({ _id: 'ref1', mime: 'text/plain' });
  const out = await adapter.download(store)({}, { file: 'ref1' }, 'id');
  assert.equal(out.fileName, 'ref1');
});

test('D8 构造期校验', () => {
  const s1 = mockStore();
  delete s1.queryOne;
  assert.throws(() => adapter.download(s1), /queryOne/);
  const s2 = mockStore();
  delete s2.resourceOpen;
  assert.throws(() => adapter.download(s2), /resourceOpen/);
  assert.throws(() => adapter.download(mockStore(), { field: '' }), /field/);
});

test('D9 upload 透传', async () => {
  const store = mockStore();
  const input = { bytes: Buffer.from('x'), fileName: 'a.txt' };
  const out = await adapter.upload(store)(input);
  assert.deepEqual(store.calls.find((c) => c[0] === 'resourcePut'), ['resourcePut', input]);
  assert.deepEqual(out, { resourceId: 'sha1', sha1: 'sha1', locations: [] });
  const s2 = mockStore();
  delete s2.resourcePut;
  assert.throws(() => adapter.upload(s2), /resourcePut/);
});

test('D10 点路径取值', async () => {
  const store = mockStore();
  await adapter.download(store, { field: 'images.original' })({}, { images: { original: 'ref3' } }, 'id');
  assert.equal(store.calls.find((c) => c[0] === 'resourceOpen')[1], 'ref3');
});

test('D11 请求级 ?field 优先于构造期 field', async () => {
  const store = mockStore();
  await adapter.download(store, { field: 'file' })(
    { query: { field: 'images.original' } },
    { file: 'ref0', images: { original: 'ref1' } },
    'id',
  );
  assert.equal(store.calls.find((c) => c[0] === 'resourceOpen')[1], 'ref1');
});

test('D12 uploadResolver 正常路径（落库入参 + 返回 ref）', async () => {
  const store = mockStore();
  const out = await adapter.uploadResolver(store, { kind: 'image' })(
    { body: Buffer.from('hi'), query: { fileName: 'a.png', mime: 'image/png' }, headers: {} },
    { _id: 'ART1' },
    'ART1',
  );
  const put = store.calls.find((c) => c[0] === 'resourcePut')[1];
  assert.deepEqual(put.bytes, Buffer.from('hi'));
  assert.equal(put.kind, 'image');
  assert.equal(put.fileName, 'a.png');
  assert.equal(put.mime, 'image/png');
  assert.deepEqual(out, { ref: 'sha1' });
});

test('D13 uploadResolver 空体抛错且零落库', async () => {
  const store = mockStore();
  await assert.rejects(
    () => adapter.uploadResolver(store)({ body: Buffer.alloc(0), headers: {} }, {}, 'id'),
    /上传字节体/,
  );
  assert.equal(store.calls.some((c) => c[0] === 'resourcePut'), false);
});

test('D14 uploadResolver 构造期校验', () => {
  const s1 = mockStore();
  delete s1.resourcePut;
  assert.throws(() => adapter.uploadResolver(s1), /resourcePut/);
  assert.throws(() => adapter.uploadResolver(mockStore(), { kind: '' }), /kind/);
  assert.throws(() => adapter.uploadResolver(mockStore(), { bind: 'x' }), /bind/);
});

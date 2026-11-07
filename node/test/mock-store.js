'use strict';

/**
 * 记录调用的最小宿主替身；同步门面返回直接值，异步门面返回 Promise。
 * opts.batch / opts.unregister 控制是否提供宿主新门面（默认均无 = 旧宿主）；
 * opts.failBatch 注入一次批量注册失败；opts.failUnregister 注入补偿失败。
 */
function mockStore(seed = {}, opts = {}) {
  const calls = [];
  // seed 支持两种形状：表名数组（conformance）或 {name: defn} 对象（单测）
  const registered = new Map(
    Array.isArray(seed) ? seed.map((n) => [n, true]) : Object.entries(seed),
  );
  let batchFailures = opts.failBatch ? 1 : 0;
  const store = {
    calls,
    has(name) {
      return registered.has(name);
    },
    register(defn) {
      calls.push(['register', defn.name]);
      registered.set(defn.name, defn);
    },
    configureResource(cfg) {
      calls.push(['configureResource', cfg]);
      return { pool: 'stub' };
    },
    registerProvider(kind, mod) {
      calls.push(['registerProvider', kind, mod]);
    },
    async resourceOpen(id, opts) {
      calls.push(['resourceOpen', id, opts]);
      // 元数据（fileName/mime）由宿主 resourceOpen 附带返回（下载不再自建 Resource 查询）
      return { bytes: Buffer.from('hello'), resourceId: id, backend: 'local', key: 'k', fileName: 'a.txt', mime: 'text/plain' };
    },
    async resourcePut(input) {
      calls.push(['resourcePut', input]);
      return { resourceId: 'sha1', sha1: 'sha1', locations: [] };
    },
  };
  if (opts.unregister) {
    store.unregister = (name) => {
      calls.push(['unregister', name]);
      if (opts.failUnregister) throw new Error('补偿失败');
      registered.delete(name);
    };
  }
  if (opts.batch) {
    store.registerBatch = (items) => {
      calls.push(['registerBatch', items.map((it) => it.defn.name)]);
      if (batchFailures > 0) {
        batchFailures -= 1;
        throw new Error('注入失败');
      }
      for (const { defn } of items) registered.set(defn.name, defn);
    };
  }
  return store;
}

module.exports = { mockStore };

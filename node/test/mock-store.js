'use strict';

/** 记录调用的最小宿主替身；同步门面返回直接值，异步门面返回 Promise。 */
function mockStore(seed = {}) {
  const calls = [];
  // seed 支持两种形状：表名数组（conformance）或 {name: defn} 对象（单测）
  const registered = new Map(
    Array.isArray(seed) ? seed.map((n) => [n, true]) : Object.entries(seed),
  );
  return {
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
    async resourceOpen(id, opts) {
      calls.push(['resourceOpen', id, opts]);
      return { bytes: Buffer.from('hello'), resourceId: id, backend: 'local', key: 'k' };
    },
    async resourcePut(input) {
      calls.push(['resourcePut', input]);
      return { resourceId: 'sha1', sha1: 'sha1', locations: [] };
    },
    async queryOne(gql, params) {
      calls.push(['queryOne', gql, params]);
      return { _id: params.c0._id, fileName: 'a.txt', mime: 'text/plain' };
    },
  };
}

module.exports = { mockStore };

'use strict';

/* ---- 依赖（仅仓内，零宿主） ---- */
const { RESOURCE_SCHEMAS } = require('./schemas');
const providers = require('./providers');

/* ---- 常量 ---- */
const CAPABILITY_FACADES = ['register', 'has', 'configureResource'];
const ALLOWED_OPTS = ['providers', 'url', 'sign', 'schema', 'providerPlugins'];
const DEFAULT_SCHEMA_NAMES = {
  resource: 'Resource',
  location: 'ResourceLocation',
  binding: 'ResourceBinding',
};

/* ---- 公共校验 ---- */

function assertStore(store, facades, where) {
  if (store === null || typeof store !== 'object') {
    throw new Error(`${where}: store 必填`);
  }
  for (const name of facades) {
    if (typeof store[name] !== 'function') {
      throw new Error(`${where}: store 缺少门面方法: ${name}`);
    }
  }
}

function assertKnownKeys(opts, where) {
  for (const key of Object.keys(opts)) {
    if (!ALLOWED_OPTS.includes(key)) {
      throw new Error(`${where}: 未知配置键: ${key}`);
    }
  }
}

/* ---- capability：能力引导 ---- */

function schemas() {
  // 深拷贝：调用方改写不得影响内部定义
  return RESOURCE_SCHEMAS.map((defn) => JSON.parse(JSON.stringify(defn)));
}

function create(store, opts = {}) {
  assertStore(store, CAPABILITY_FACADES, 'capability.create');
  assertKnownKeys(opts, 'capability.create');

  const providers = opts.providers;
  if (!Array.isArray(providers) || providers.length === 0) {
    throw new Error('capability.create: providers 必填且须为非空数组');
  }
  providers.forEach((spec, i) => {
    if (spec === null || typeof spec !== 'object') {
      throw new Error(`capability.create: providers[${i}] 须为对象`);
    }
    if (typeof spec.kind !== 'string' || spec.kind === '') {
      throw new Error(`capability.create: providers[${i}].kind 须为非空字符串`);
    }
    if (spec.options !== undefined && (spec.options === null || typeof spec.options !== 'object')) {
      throw new Error(`capability.create: providers[${i}].options 须为对象`);
    }
    if (spec.priority !== undefined && !Number.isInteger(spec.priority)) {
      throw new Error(`capability.create: providers[${i}].priority 须为整数`);
    }
  });

  const url = opts.url === undefined ? {} : opts.url;
  if (url === null || typeof url !== 'object') {
    throw new Error('capability.create: url 须为对象');
  }
  const sign = opts.sign === undefined ? null : opts.sign;
  if (sign !== null && typeof sign !== 'function') {
    throw new Error('capability.create: sign 须为函数或 null');
  }
  const schema = opts.schema === undefined ? { ...DEFAULT_SCHEMA_NAMES } : opts.schema;
  if (schema === null || typeof schema !== 'object') {
    throw new Error('capability.create: schema 须为对象');
  }
  const providerPlugins = opts.providerPlugins === undefined ? [] : opts.providerPlugins;
  if (!Array.isArray(providerPlugins)) {
    throw new Error('capability.create: providerPlugins 须为数组');
  }
  providerPlugins.forEach((spec, i) => {
    if (spec === null || typeof spec !== 'object') {
      throw new Error(`capability.create: providerPlugins[${i}] 须为对象`);
    }
    if (typeof spec.kind !== 'string' || spec.kind === '') {
      throw new Error(`capability.create: providerPlugins[${i}].kind 须为非空字符串`);
    }
    if (typeof spec.create !== 'function') {
      throw new Error(`capability.create: providerPlugins[${i}].create 须为函数`);
    }
  });
  // 条件化门面校验：仅当有 provider 需要注册时才要求宿主门面（向后兼容旧 store）
  if (providerPlugins.length > 0) {
    assertStore(store, ['registerProvider'], 'capability.create');
  }

  async function start() {
    const registered = [];
    const skipped = [];
    const providerRegistered = [];
    for (const spec of providerPlugins) {
      store.registerProvider(spec.kind, { create: spec.create });  // registerProvider 为同步门面
      providerRegistered.push(spec.kind);
    }
    for (const defn of schemas()) {
      if (store.has(defn.name)) {
        skipped.push(defn.name);   // has 为同步门面
      } else {
        store.register(defn);      // register 为同步门面，幂等
        registered.push(defn.name);
      }
    }
    await store.configureResource({ providers, url, sign, schema });  // configureResource 为同步实现，await 兼容
    return { registered, skipped, providerRegistered };
  }

  return {
    start,
    // 宿主 configure 整体替换 _pool，故 reload ≡ start（无需先清除）
    async reload() {
      return start();
    },
  };
}

/* ---- adapter：接缝适配 ---- */

const RESOURCE_PROJECTION = ' { _id, fileName, mime }';  // 投影语法同 store-api/node/src/plugin.js L109

function download(store, opts = {}) {
  assertStore(store, ['resourceOpen', 'queryOne'], 'adapter.download');
  if (opts === null || typeof opts !== 'object') {
    throw new Error('adapter.download: opts 须为对象');
  }
  const field = opts.field === undefined ? 'file' : opts.field;
  if (typeof field !== 'string' || field === '') {
    throw new Error('adapter.download: field 须为非空字符串');
  }
  const order = opts.order;

  // 返回 store-api 既有 fileResolver 契约：(req, rec, id) => {body, contentType, fileName}
  return async function fileResolver(req, rec, id) {
    const ref = rec == null ? null : rec[field];
    if (ref === undefined || ref === null || ref === '') {
      throw new Error(`记录缺少资源引用字段: ${field}`);
    }
    const opened = await store.resourceOpen(ref, order === undefined ? {} : { order });
    const meta = await store.queryOne(
      `Resource($condition: @c0)${RESOURCE_PROJECTION}`,
      { c0: { _id: ref } },
    );
    return {
      body: opened.bytes,
      contentType: (meta && meta.mime) || 'application/octet-stream',
      fileName: (meta && meta.fileName) || String(ref),
    };
  };
}

function upload(store) {
  assertStore(store, ['resourcePut'], 'adapter.upload');
  // 薄透传：不改写入参、不改写出参
  return async function upload_(input) {
    return store.resourcePut(input);
  };
}

module.exports = {
  capability: { schemas, create },
  adapter: { download, upload },
  providers,
};

'use strict';

const base = require('./s3-compat');

/** MinIO 预设：自建网关需 path-style（bucket 在路径中） */
const preset = { kind: 'minio', forcePathStyle: true };

function create(options = {}, deps) {
  return base.create({ ...preset, ...options, kind: 'minio' }, deps);
}

module.exports = { create, preset };

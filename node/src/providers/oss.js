'use strict';

const base = require('./s3-compat');

/** OSS 预设：OSS 仅支持 virtual-hosted（bucket 在域名中）；Node 走 V4（默认无需额外 config） */
const preset = { kind: 'oss', forcePathStyle: false };

function create(options = {}, deps) {
  return base.create({ ...preset, ...options, kind: 'oss' }, deps);
}

module.exports = { create, preset };

'use strict';

/**
 * 三 schema 定义（唯一事实源：spec/00-protocol.md 附录 A）。
 * 逐字复制 01 执行文档 §4.8 的 JSON 数组；conformance A9 校验本常量与源契约深比较全等。
 * 注意：Resource.idPrefix 必须为空串 ""（宿主仅当真值才生成 _id，否则破坏 resourceId = sha1）。
 */
const RESOURCE_SCHEMAS = [
  {
    name: 'Resource', collection: 'resources', idPrefix: '', timestamps: true,
    read: [], write: [],
    fields: {
      _id:      { type: 'string' },
      sha1:     { type: 'string' },
      fileName: { type: 'string' },
      mime:     { type: 'string' },
      size:     { type: 'int' },
      kind:     { type: 'string' },
    },
    relations: {},
    indexes: [
      { keys: { sha1: 1 }, options: { unique: true } },
    ],
  },
  {
    name: 'ResourceLocation', collection: 'resource_locations', idPrefix: 'rl', timestamps: true,
    read: [], write: [],
    fields: {
      _id:        { type: 'string' },
      resourceId: { type: 'string' },
      backend:    { type: 'string' },
      key:        { type: 'string' },
      status:     { type: 'string' },
      priority:   { type: 'int' },
    },
    relations: {
      resource: { model: 'Resource', type: 'one', localField: 'resourceId', foreignField: '_id', read: [] },
    },
    indexes: [
      { keys: { resourceId: 1, backend: 1 }, options: { unique: true } },
    ],
  },
  {
    name: 'ResourceBinding', collection: 'resource_bindings', idPrefix: 'rb', timestamps: true,
    read: [], write: [],
    fields: {
      _id:           { type: 'string' },
      resourceId:    { type: 'string' },
      businessTable: { type: 'string' },
      businessId:    { type: 'string' },
      userId:        { type: 'string' },
    },
    relations: {
      resource: { model: 'Resource', type: 'one', localField: 'resourceId', foreignField: '_id', read: [] },
    },
    indexes: [
      { keys: { resourceId: 1, businessTable: 1, businessId: 1 }, options: { unique: true } },
    ],
  },
];

module.exports = { RESOURCE_SCHEMAS };

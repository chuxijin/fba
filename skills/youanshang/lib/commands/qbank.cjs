'use strict';

const { authenticatedSkill } = require('../openauth.cjs');

const QUESTION_TYPES = [
  'single_choice', 'multiple_choice', 'true_false', 'fill_blank', 'short_answer', 'composite', 'interactive',
];
const BANK_KINDS = ['practice', 'paper', 'mock'];
const CATEGORY_TYPES = ['product_catalog', 'knowledge_point', 'resource_exam'];
const ID_RE = /^\d+$/;

/** 验证逗号分隔的正整数列表，返回解析后的数组或 undefined */
function optionalIdList(value, name) {
  if (value === undefined || value === null || value === '') return undefined;
  const parts = String(value).split(',').map(s => s.trim());
  if (parts.some(s => !ID_RE.test(s))) throw new Error(`INVALID_ARGUMENT: --${name} 必须是逗号分隔的正整数`);
  return parts.map(Number);
}

/**
 * skill 业务命令分发：题库目录 / 题目检索 / 题目详情 / 分类树 / 知识点树（只读）
 * @param {string} command 子命令标识：qbank-banks | qbank-search | qbank-detail | qbank-categories | qbank-knowledge-systems | qbank-knowledge-points
 * @param {{[key:string]: string}} options CLI 参数（keys 已按 entrypoint 校验）
 * @param {object} state 用户目录状态
 * @param {string} directory 用户配置目录
 * @returns {Promise<object>} 透出的业务响应
 */
async function qbank(command, options, state, directory) {
  if (!state.config?.skill_base_url) {
    throw new Error('INVALID_CONFIG: 当前授权配置版本过旧，请重新执行 login 升级服务配置');
  }
  if (command === 'qbank-categories') {
    const query = buildQuery(state, {
      app_code: optionalText(options['app-code'] || 'youanshang', 'app-code'),
      category_type: optionalEnum(options['category-type'] || 'product_catalog', CATEGORY_TYPES, 'category-type'),
      include_disabled: options['include-disabled'] ? 'true' : 'false',
    });
    return authenticatedSkill(directory, state, 'GET', `/qbank/categories${query}`, undefined);
  }
  if (command === 'qbank-knowledge-systems') {
    const query = buildQuery(state, {
      domain_category_id: optionalId(options['category-id'], 'category-id'),
      page: optionalId(options.page || '1', 'page'),
      size: optionalId(options.size || '20', 'size'),
    });
    return authenticatedSkill(directory, state, 'GET', `/qbank/knowledge-systems${query}`, undefined);
  }
  if (command === 'qbank-knowledge-points') {
    const systemId = optionalId(options['system-id'], 'system-id');
    if (!systemId) throw new Error('INVALID_ARGUMENT: qbank-knowledge-points 必须提供 --system-id <知识体系 ID>');
    return authenticatedSkill(directory, state, 'GET', `/qbank/knowledge-systems/${systemId}/points`, undefined);
  }
  if (command === 'qbank-banks') {
    const query = buildQuery(state, {
      category_id: optionalId(options['category-id'], 'category-id'),
      bank_kind: optionalEnum(options['bank-kind'], BANK_KINDS, 'bank-kind'),
      keyword: optionalText(options.keyword, 'keyword'),
      page: optionalId(options.page || '1', 'page'),
      size: optionalId(options.size || '20', 'size'),
    });
    return authenticatedSkill(directory, state, 'GET', `/qbank/banks${query}`, undefined);
  }
  if (command === 'qbank-search') {
    const query = buildQuery(state, {
      bank_id: optionalId(options['bank-id'], 'bank-id'),
      question_type: optionalEnum(options['question-type'], QUESTION_TYPES, 'question-type'),
      keyword: optionalText(options.keyword, 'keyword'),
      knowledge_point_ids: optionalIdList(options['knowledge-point-ids'], 'knowledge-point-ids'),
      page: optionalId(options.page || '1', 'page'),
      size: optionalId(options.size || '20', 'size'),
    });
    return authenticatedSkill(directory, state, 'GET', `/qbank/questions${query}`, undefined);
  }
  if (command === 'qbank-detail') {
    const id = optionalId(options.id, 'id');
    if (!id) throw new Error('INVALID_ARGUMENT: qbank-detail 必须提供 --id <题目 ID>');
    return authenticatedSkill(directory, state, 'GET', `/qbank/questions/${id}`, undefined);
  }
  throw new Error(`UNSUPPORTED_COMMAND: unknown qbank command ${command}`);
}

/** @returns {string} 拼接查询串；参数为空时省略 */
function buildQuery(state, entries) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(entries)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value));
  }
  const text = params.toString();
  return text ? `?${text}` : '';
}

function optionalId(value, name) {
  if (value === undefined || value === null || value === '') return undefined;
  if (!ID_RE.test(String(value))) throw new Error(`INVALID_ARGUMENT: --${name} 必须是正整数`);
  return Number(String(value));
}

function optionalEnum(value, allowed, name) {
  if (value === undefined || value === null || value === '') return undefined;
  if (!allowed.includes(String(value))) {
    throw new Error(`INVALID_ARGUMENT: --${name} 必须是 ${allowed.join(' | ')}`);
  }
  return String(value);
}

function optionalText(value, name) {
  if (value === undefined || value === null || value === '') return undefined;
  return String(value);
}

module.exports = { qbank, QUESTION_TYPES, BANK_KINDS, CATEGORY_TYPES };

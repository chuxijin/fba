'use strict';

const { authenticatedSkill } = require('../openauth.cjs');

const KIND_RE = /^[a-z][a-z-]{0,63}$/;
const KINDS = ['basic', 'fill-blank', 'data-practice', 'advanced'];

/**
 * skill 业务命令分发：计算练习目录 / 生成 / 导出
 * @param {string} command 子命令标识：calc-catalog | calc-generate | calc-export
 * @param {{[key:string]: string}} options CLI 参数（keys 已按 entrypoint 校验）
 * @param {object} state 用户目录状态
 * @param {string} directory 用户配置目录
 * @returns {Promise<object>} 透出的业务响应
 */
async function calculation(command, options, state, directory) {
  if (!state.config?.skill_base_url) {
    throw new Error('INVALID_CONFIG: 当前授权配置版本过旧，请重新执行 login 升级服务配置');
  }
  if (command === 'calc-catalog') {
    return authenticatedSkill(directory, state, 'GET', '/calculation/catalog', undefined);
  }
  if (command === 'calc-generate' || command === 'calc-export') {
    const kind = options.kind;
    if (!kind || !KINDS.includes(kind)) {
      throw new Error(`INVALID_ARGUMENT: --kind 必须是 ${KINDS.join(' | ')}`);
    }
    let params = {};
    if (options.params) {
      try { params = JSON.parse(String(options.params)); }
      catch { throw new Error('INVALID_ARGUMENT: --params 必须是合法 JSON 对象（不要传数组或字符串）'); }
    }
    if (typeof params !== 'object' || params === null || Array.isArray(params)) {
      throw new Error('INVALID_ARGUMENT: --params 必须是 JSON 对象，不含括号数组');
    }
    if (command === 'calc-generate') {
      return authenticatedSkill(directory, state, 'POST', `/calculation/${kind}/generate`, params);
    }
    return authenticatedSkill(directory, state, 'POST', '/calculation/export', {
      kind,
      params,
      title: options.title || '计算练习',
      answer_layout: options.answer_layout,
    });
  }
  throw new Error(`UNSUPPORTED_COMMAND: unknown calculation command ${command}`);
}

module.exports = { calculation, KINDS };

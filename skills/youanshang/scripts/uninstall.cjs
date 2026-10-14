#!/usr/bin/env node
'use strict';
const fs = require('node:fs/promises');
const path = require('node:path');
const { CliError, configDirectory, withLock, request } = require('../lib/openauth.cjs');

async function main() {
  const args = process.argv.slice(2);
  const options = {};
  if (args.length) {
    if (args.length !== 2 || args[0] !== '--config-dir' || !args[1]) throw new CliError('INVALID_ARGUMENT', '卸载参数无效');
    options['config-dir'] = args[1];
  }
  const directory = await configDirectory(options);
  await withLock(directory, async state => {
    // 与 CLI logout 使用同一安全端点，但在同一锁下完成撤销和文件清理，避免并发新登录被删除。
    if (state.tokens) await request(state.config, '/logout', { token: state.tokens.access_token });
    const filename = path.resolve(directory, 'state.json');
    if (path.dirname(filename) !== directory) throw new CliError('UNSAFE_STORAGE', '拒绝清理非目标路径');
    await fs.rm(filename, { force: true });
  });
  // 不递归删除：只删除自己的已清空目录。显式 config-dir 中用户的其他文件保持原状。
  try { await fs.rmdir(directory); } catch (error) { if (!['ENOTEMPTY', 'EEXIST', 'ENOENT'].includes(error.code)) throw error; }
  console.log(JSON.stringify({ type: 'result', code: 0, ok: true,
    msg: '本机授权与当前配置已清理。Skill 文件保留，请由 Agent 移除 youanshang Skill 目录。', data: {} }));
}
main().catch(error => {
  console.log(JSON.stringify({ type: 'result', code: -1, ok: false,
    msg: error instanceof CliError ? error.message : '卸载失败，未确认远端撤销；请保留 Skill 和配置后重试', data: {} }));
  process.exitCode = 1;
});

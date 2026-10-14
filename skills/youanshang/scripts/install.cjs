#!/usr/bin/env node
'use strict';
const fs = require('node:fs/promises');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { CliError, trustedUrl, validateConfig, withLock, configDirectory, writeState } = require('../lib/openauth.cjs');
const { FILES, fetchBytes, validateRelease, extractVerified, matches, installFiles } = require('../lib/package.cjs');
const runtime = require('../runtime.json');

async function main() {
  if (Number(process.versions.node.split('.')[0]) < 22) throw new CliError('NODE_VERSION', '请安装 Node.js 22+ 后重试');
  const args = process.argv.slice(2);
  if (args.includes('--help')) { console.log('bash scripts/install.sh [--destination 全局skills目录] [--config-dir DIR] [--force]\n默认检查本地服务版本，自动同步完整 Skill。--destination 仅复制整个本地包。'); return; }
  const options = {};
  for (let i = 0; i < args.length; i++) {
    const key = args[i].replace(/^--/, '');
    if (!args[i].startsWith('--') || !['destination', 'config-dir', 'force', 'update'].includes(key) || key in options)
      throw new CliError('INVALID_ARGUMENT', '安装参数无效');
    if (['force', 'update'].includes(key)) options[key] = true;
    else {
      if (!args[i + 1] || args[i + 1].startsWith('--')) throw new CliError('INVALID_ARGUMENT', '安装参数缺少值');
      options[key] = args[++i];
    }
  }
  const source = path.resolve(__dirname, '..');
  const directory = await configDirectory(options);
  console.log(`[info] 运行环境 ${process.platform}/${process.arch}；Node.js ${process.version}`);
  await withLock(directory, async state => {
    let installed = false;
    let root = source;
    if (options.destination) {
      root = path.join(path.resolve(options.destination), 'youanshang');
      if (root === source) throw new CliError('INVALID_TARGET', '无需安装到源目录自身');
      await fs.mkdir(path.dirname(root), { recursive: true });
      try { await fs.mkdir(root); }
      catch (error) { if (error.code !== 'EEXIST' || !options.update) throw error; }
      const files = new Map();
      for (const name of FILES) files.set(name, await fs.readFile(path.join(source, name)));
      await installFiles(root, files);
      installed = true;
    } else {
      // 安装源仅取随可信包分发的公开配置，不从查询结果或账号状态中接收任意下载地址。
      const base = trustedUrl(runtime.api_base_url).href.replace(/\/$/, '');
      const envelope = JSON.parse((await fetchBytes(`${base}/skill-config`, 100000)).toString('utf8'));
      if (envelope.code !== 200) throw new CliError('INSTALL_RESPONSE', '获取 Skill 发布信息失败');
      const release = validateRelease(envelope.data);
      if (options.force || !(await matches(root, release))) {
        console.log(`[info] 下载并验证完整 Skill ${release.version}`);
        const zip = await fetchBytes(`${base}/${release.package_path}`, 8 * 1024 * 1024);
        await installFiles(root, extractVerified(zip, release));
        installed = true;
      } else console.log(`[info] 当前已是最新版本 ${release.version}，完成环境自检`);
    }
    // 校验只读版本，不发起登录、业务调用，也不读取用户凭据到 stdout。
    const config = JSON.parse(await fs.readFile(path.join(root, 'runtime.json'), 'utf8'));
    const check = spawnSync(process.execPath, [path.join(root, 'scripts/youanshang.cjs'), '--version'],
      { encoding: 'utf8', windowsHide: true, timeout: 10000 });
    if (check.status !== 0 || check.stdout.trim() !== config.version) throw new CliError('VERIFY_FAILED', '安装自检失败');
    if (!state.config) state.config = validateConfig(config);
    const showWelcome = !state.tokens && !state.welcome_shown;
    if (showWelcome) state.welcome_shown = true;
    await writeState(directory, state);
    console.log(JSON.stringify({ type: 'result', code: 0, ok: true, msg: '环境准备完成', data: {
      installed, version: config.version, path: root, files: FILES.length, show_welcome: showWelcome,
    } }));
    if (showWelcome) console.log(JSON.stringify({ type: 'welcome', code: 0,
      msg: require(path.join(root, 'lib/messages.cjs')).welcome, data: {} }));
  });
}

main().catch(error => {
  console.log(JSON.stringify({ type: 'result', code: -1, ok: false,
    msg: error instanceof CliError ? error.message : '环境准备失败，请检查服务、安装包及目录权限', data: {} }));
  process.exitCode = 1;
});

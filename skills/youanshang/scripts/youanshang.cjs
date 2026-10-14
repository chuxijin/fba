#!/usr/bin/env node
'use strict';
const { run, CliError, readState, configDirectory, defaultDirectory } = require('../lib/openauth.cjs');
const { calculation } = require('../lib/commands/calculation.cjs');
const { qbank } = require('../lib/commands/qbank.cjs');

const help = `youanshang CLI（Node.js >= 22，无额外依赖）
  configure --api-base-url URL --authorize-url URL --client-id ID [--scope "profile:read"]
            [--redirect-uri http://127.0.0.1:17888/callback]
  login [--token 授权码 | --no-browser | --manual | --callback-url 完整回调地址]
  check           验证当前身份和权限
  profile         查看当前授权账号的最小资料
  get-user-info   查看账号资料（推荐命令，含 skill 会员态）
  unauthorize     返回解除当前设备授权的网页链接，等待本人确认
  status          查看本地配置状态（不显示凭据）
  logout          仅供 uninstall.sh 内部撤销本机授权
  cancel-login    清除尚未完成的本地授权流程
  calc-catalog                             计算练习题型与参数目录（动态查询）
  calc-generate --kind KIND [--params JSON]生成计算练习：basic | fill-blank | data-practice | advanced
  calc-export --kind KIND [--params JSON] [--title "题本标题"]  同 seed 重生成导出 PDF（回显下载路径）
  qbank-banks [--category-id ID] [--bank-kind practice|paper|mock] [--keyword 词] [--page N] [--size N]
              已发布题库目录（只读）
  qbank-search [--bank-id ID] [--question-type 题型] [--keyword 词] [--knowledge-point-ids id1,id2,...] [--page N] [--size N]
              检索题库题目（只读，不含答案解析，可按知识点过滤）
  qbank-detail --id 题目ID   题目详情（含选项、答案、解析、知识点）
  qbank-categories [--app-code 应用] [--category-type product_catalog|knowledge_point|resource_exam]
              题库分类树（只读，拿 category_id 给 qbank-banks 用）
  qbank-knowledge-systems [--category-id 领域分类ID]
              知识体系列表（只读，拿 system_id 给 qbank-knowledge-points 用）
  qbank-knowledge-points --system-id 知识体系ID
              知识点树（只读，拿 knowledge_point_ids 给 qbank-search 用）
所有子命令支持 --session-input 原始提问 --session-id 时间戳-随机串。
测试可传 --config-dir DIR 指定独立用户配置目录。无须 configure，本地服务配置已随包提供。
标准输出为 NDJSON；凭据不会输出到终端。`;

async function main() {
  if (Number(process.versions.node.split('.')[0]) < 22) throw new CliError('NODE_VERSION', '请使用 Node.js 22 或更新版本');
  const [command, ...args] = process.argv.slice(2);
  if (command === '--version') { console.log(require('../runtime.json').version); return; }
  if (!command || ['--help', '-h', 'help'].includes(command)) { console.log(help); return; }
  const allowed = {
    configure: ['api-base-url', 'authorize-url', 'client-id', 'scope', 'redirect-uri'],
    login: ['token', 'no-browser', 'manual', 'callback-url'], check: [], profile: [], 'get-user-info': [],
    unauthorize: [], status: [], logout: ['local-only'], 'cancel-login': [],
    'calc-catalog': [], 'calc-generate': ['kind', 'params', 'out'], 'calc-export': ['kind', 'params', 'title'],
    'qbank-banks': ['category-id', 'bank-kind', 'keyword', 'page', 'size'],
    'qbank-search': ['bank-id', 'question-type', 'keyword', 'knowledge-point-ids', 'page', 'size'],
    'qbank-search': ['bank-id', 'question-type', 'keyword', 'knowledge-point-ids', 'page', 'size'],
    'qbank-detail': ['id'],
    'qbank-categories': ['app-code', 'category-type', 'include-disabled'],
    'qbank-knowledge-systems': ['category-id', 'page', 'size'],
    'qbank-knowledge-points': ['system-id'],
  };
  if (!allowed[command]) throw new CliError('UNKNOWN_COMMAND', '未知命令，请使用 --help');
  const options = {};
  for (let i = 0; i < args.length; i++) {
    const key = args[i].replace(/^--/, '');
    if (!args[i].startsWith('--') || !['config-dir', 'session-input', 'session-id', ...allowed[command]].includes(key) || key in options)
      throw new CliError('INVALID_ARGUMENT', '存在未知或重复参数');
    if (['manual', 'no-browser', 'local-only'].includes(key)) options[key] = true;
    else {
      if (!args[i + 1] || args[i + 1].startsWith('--')) throw new CliError('INVALID_ARGUMENT', '参数缺少值');
      options[key] = args[++i];
    }
  }
  if (['manual', 'no-browser', 'callback-url', 'token'].filter(key => options[key]).length > 1)
    throw new CliError('INVALID_ARGUMENT', '请选择一种登录方式');
  if (options['session-id'] && !/^\d{10,}-[a-zA-Z0-9]{6}$/.test(options['session-id']))
    throw new CliError('INVALID_ARGUMENT', 'session-id 格式必须为 Unix秒时间戳-6位随机字母数字');
  // 接受与参考 Skill 相同的公共参数，但不默认持久化或上传用户原始提问。
  const emit = result => console.log(JSON.stringify(result));

  if (command.startsWith('calc-')) {
    const directory = options['config-dir'] || process.env.YOUANSHANG_CONFIG_DIR || await defaultDirectory();
    const state = await readState(directory);
    if (!state.tokens) {
      emit({ type: 'result', ok: false, code: -1408, reason: 'AUTH_REQUIRED', msg: '尚未授权，请先 login', data: {} });
      return;
    }
    const data = await calculation(command, options, state, directory);
    emit({ type: 'result', code: 0, msg: data?.msg || '操作成功', ok: true, action: command, data });
    return;
  }

  if (command.startsWith('qbank-')) {
    const directory = options['config-dir'] || process.env.YOUANSHANG_CONFIG_DIR || await defaultDirectory();
    const state = await readState(directory);
    if (!state.tokens) {
      emit({ type: 'result', ok: false, code: -1408, reason: 'AUTH_REQUIRED', msg: '尚未授权，请先 login', data: {} });
      return;
    }
    const data = await qbank(command, options, state, directory);
    emit({ type: 'result', code: 0, msg: data?.msg || '操作成功', ok: true, action: command, data });
    return;
  }

  const data = await run(command, options, emit);
  emit({ type: 'result', code: 0, msg: data?.msg || '操作成功', ok: true, action: command, data });
}

main().catch(error => {
  console.log(JSON.stringify({ type: 'result', ok: false,
    code: error instanceof CliError && error.code === 'AUTH_REQUIRED' ? -1408 : -1,
    reason: error instanceof CliError ? error.code : 'LOCAL_ERROR',
    msg: error instanceof CliError ? error.message : '本地操作失败，请检查目录权限或服务状态；没有输出敏感错误内容',
    data: error instanceof CliError ? (error.data || {}) : {} }));
  process.exitCode = 1;
});

'use strict';

const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const http = require('node:http');
const { spawn, execFileSync } = require('node:child_process');
const runtime = require('../runtime.json');

class CliError extends Error {
  constructor(code, message, status = 0) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

const fail = (code, message) => { throw new CliError(code, message); };
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const random = () => crypto.randomBytes(32).toString('base64url');
const challenge = verifier => crypto.createHash('sha256').update(verifier).digest('base64url');

function trustedUrl(raw) {
  let url;
  try { url = new URL(raw); } catch { fail('INVALID_CONFIG', '配置中存在无效地址'); }
  if (url.username || url.password || url.hash || url.search || /[\s\\]/.test(raw)
    || !(url.protocol === 'https:' || (url.protocol === 'http:'
      && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)))) {
    fail('INVALID_CONFIG', '服务地址必须为 HTTPS；只有本机地址可以使用 HTTP，且不能含凭据或查询参数');
  }
  return url;
}

function validateConfig(config) {
  if (!config || typeof config.client_id !== 'string' || !config.client_id.trim())
    fail('NOT_CONFIGURED', '请先配置服务地址和管理员提供的 client_id');
  const api = trustedUrl(config.api_base_url);
  const authorize = trustedUrl(config.authorize_url);
  const redirect = trustedUrl(config.redirect_uri);
  if (redirect.protocol !== 'http:' || redirect.hostname !== '127.0.0.1' || !redirect.port
    || redirect.pathname !== '/callback') {
    fail('INVALID_CONFIG', '本版本回调地址必须是 http://127.0.0.1:固定端口/callback');
  }
  if (!Array.isArray(config.scopes) || !config.scopes.length
    || !config.scopes.every(s => typeof s === 'string' && /^[a-z][a-z0-9:_-]{0,99}$/.test(s)))
    fail('INVALID_CONFIG', '必须配置非空的合法权限列表');
  const skillBase = config.skill_base_url ? trustedUrl(config.skill_base_url).href.replace(/\/$/, '') : null;
  return {
    api_base_url: api.href.replace(/\/$/, ''), authorize_url: authorize.href,
    redirect_uri: redirect.href, client_id: config.client_id.trim(), scopes: [...new Set(config.scopes)],
    skill_base_url: skillBase,
  };
}

async function defaultDirectory(root = process.env.LOCALAPPDATA || path.join(os.homedir(), '.config')) {
  const preferred = path.join(root, 'youanshang-skill');
  // 已使用旧版的用户继续使用原目录及进程锁，不复制令牌、不自动丢失登录态。
  for (const candidate of [preferred, path.join(root, 'gongkao-skill')]) {
    try {
      const stat = await fs.lstat(candidate);
      if (!stat.isDirectory() || stat.isSymbolicLink()) fail('UNSAFE_STORAGE', '凭据目录必须是普通目录');
      return candidate;
    } catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  return preferred;
}

async function configDirectory(options = {}) {
  return path.resolve(options['config-dir'] || process.env.YOUANSHANG_CONFIG_DIR || await defaultDirectory());
}

function manualCode(code, pending, now = Date.now()) {
  if (!pending || now - pending.created_at > 600000 || typeof pending.verifier !== 'string')
    fail('LOGIN_EXPIRED', '没有本机待授权会话或会话已过期，请重新发起登录');
  if (typeof code !== 'string' || !/^[A-Za-z0-9_-]{20,512}$/.test(code))
    fail('INVALID_CALLBACK', '授权码格式无效，请复制回调地址中的 code 参数值');
  // 手动 code 不声称已验证 state；服务端强制 S256，将 code 绑定到本机保留的 verifier。
  return code;
}

async function ensurePrivateDirectory(directory) {
  await fs.mkdir(directory, { recursive: true, mode: 0o700 });
  const stat = await fs.lstat(directory);
  if (!stat.isDirectory() || stat.isSymbolicLink()) fail('UNSAFE_STORAGE', '凭据目录必须是普通目录，不能是符号链接');
  if (process.platform === 'win32') {
    // Windows chmod 无法设置 ACL。按当前登录主体限制继承和访问，不调用 shell。
    try {
      const account = execFileSync('whoami.exe', [], { encoding: 'utf8', windowsHide: true }).trim();
      execFileSync('icacls.exe', [directory, '/inheritance:r', '/grant:r', `${account}:(OI)(CI)F`],
        { stdio: 'ignore', windowsHide: true });
    } catch { fail('UNSAFE_STORAGE', '无法限制凭据目录权限，已停止保存登录信息'); }
  } else await fs.chmod(directory, 0o700);
}

async function readState(directory) {
  const filename = path.join(directory, 'state.json');
  try {
    const stat = await fs.lstat(filename);
    if (!stat.isFile() || stat.isSymbolicLink()) fail('UNSAFE_STORAGE', '凭据文件不是普通文件');
    return JSON.parse(await fs.readFile(filename, 'utf8'));
  } catch (error) {
    if (error.code === 'ENOENT') return { version: 1 };
    if (error instanceof CliError) throw error;
    fail('INVALID_STORAGE', '本地配置损坏，请保留文件并检查，不要把凭据内容贴到对话中');
  }
}

async function writeState(directory, state) {
  const temporary = path.join(directory, `.state-${random()}.tmp`);
  const handle = await fs.open(temporary, 'wx', 0o600);
  try {
    await handle.writeFile(JSON.stringify(state, null, 2), 'utf8');
    await handle.sync();
  } finally { await handle.close(); }
  try { await fs.rename(temporary, path.join(directory, 'state.json')); }
  finally { await fs.rm(temporary, { force: true }); }
}

async function withLock(directory, callback, waitMs = 15000) {
  await ensurePrivateDirectory(directory);
  const lockPath = path.join(directory, 'state.lock');
  const deadline = Date.now() + waitMs;
  let handle;
  while (!handle) {
    try {
      handle = await fs.open(lockPath, 'wx', 0o600);
      await handle.writeFile(JSON.stringify({ pid: process.pid, owner: random() }));
    } catch (error) {
      if (handle) { await handle.close(); await fs.rm(lockPath, { force: true }); throw error; }
      if (error.code !== 'EEXIST') throw error;
      try {
        const stat = await fs.lstat(lockPath);
        if (!stat.isFile() || stat.isSymbolicLink()) fail('UNSAFE_STORAGE', '锁文件不安全');
        const lock = JSON.parse(await fs.readFile(lockPath, 'utf8'));
        if (Number.isSafeInteger(lock.pid) && lock.pid > 0) {
          try { process.kill(lock.pid, 0); }
          catch (probe) {
            if (probe.code === 'ESRCH') fail('STALE_LOCK', '发现已退出进程的锁；确认没有其他 CLI 运行后，仅删除 state.lock，再重试');
          }
        }
      } catch (error) { if (error instanceof CliError) throw error; }
      if (Date.now() >= deadline) fail('BUSY', '另一个命令正在登录或刷新，请等待它结束后重试');
      await sleep(100);
    }
  }
  try { return await callback(await readState(directory)); }
  finally { await handle.close(); await fs.rm(lockPath, { force: true }); }
}

async function request(config, endpoint, { body, token, method = 'POST', baseUrl } = {}) {
  let response;
  const base = baseUrl && typeof baseUrl === 'string' ? baseUrl : config.api_base_url;
  try {
    response = await fetch(`${base}${endpoint}`, {
      method, redirect: 'error', signal: AbortSignal.timeout(method === 'GET' ? 15000 : 120000),
      headers: { Accept: 'application/json', ...(body ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch { fail('NETWORK_ERROR', '服务连接失败或超时；不会自动重复提交授权码或刷新令牌'); }
  let result;
  try { result = await response.json(); }
  catch { fail('INVALID_RESPONSE', '服务返回了非预期响应'); }
  if (!response.ok || result.code !== 200) {
    const status = response.ok ? result.code : response.status;
    if (status === 401) throw new CliError('AUTH_REQUIRED', '授权已失效，请重新登录', 401);
    if (status === 403 || status === 422) {
      // 业务侧权限/参数校验消息必须原样透出，Agent 据此引导用户或自纠参数
      throw new CliError(String(status), String(result.msg || `服务拒绝请求（${status}）`), status);
    }
    throw new CliError('API_ERROR', `服务拒绝请求（${Number(status) || '未知状态'}），请检查权限或服务状态`, status);
  }
  return result.data;
}

function pendingLogin(config, now = Date.now()) {
  const pending = { state: random(), verifier: random(), created_at: now };
  const url = new URL(config.authorize_url);
  url.search = new URLSearchParams({
    client_id: config.client_id, scope: config.scopes.join(' '), redirect_uri: config.redirect_uri,
    state: pending.state, code_challenge: challenge(pending.verifier), code_challenge_method: 'S256',
  }).toString();
  return { pending, url: url.href };
}

function parseCallback(raw, config, pending, now = Date.now()) {
  if (!pending || now - pending.created_at > 600000) fail('LOGIN_EXPIRED', '待授权会话已过期，请重新发起登录');
  let url;
  try { url = new URL(raw); } catch { fail('INVALID_CALLBACK', '请使用完整回调地址，不能只提供 code'); }
  const expected = new URL(config.redirect_uri);
  const states = url.searchParams.getAll('state');
  const state = states[0] || '';
  if (url.origin !== expected.origin || url.pathname !== expected.pathname || url.hash || url.username || url.password
    || states.length !== 1 || Buffer.byteLength(state) !== Buffer.byteLength(pending.state)
    || !crypto.timingSafeEqual(Buffer.from(state), Buffer.from(pending.state))) {
    fail('INVALID_CALLBACK', '回调地址或 state 校验失败，未交换任何凭据');
  }
  const codes = url.searchParams.getAll('code');
  const errors = url.searchParams.getAll('error');
  if (errors.length === 1 && errors[0] === 'access_denied' && !codes.length)
    fail('ACCESS_DENIED', '你已取消本次授权');
  if (errors.length || codes.length !== 1 || !/^[A-Za-z0-9_-]{20,512}$/.test(codes[0]))
    fail('INVALID_CALLBACK', '授权回调缺少合法授权码');
  return codes[0];
}

function openBrowser(url) {
  const command = process.platform === 'win32' ? 'rundll32.exe' : process.platform === 'darwin' ? 'open' : 'xdg-open';
  const args = process.platform === 'win32' ? ['url.dll,FileProtocolHandler', url] : [url];
  const child = spawn(command, args, { stdio: 'ignore', detached: true, windowsHide: true });
  child.on('error', () => {}); // 授权链接始终另行输出，浏览器无法启动时可手动打开。
  child.unref();
}

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function renderCallbackHtml({ status, title, subtitle, message, autoCloseSeconds = 0 }) {
  const isSuccess = status === 'success';
  const isCancelled = status === 'cancelled';
  let iconSvg = '';
  let themeClass = '';
  if (isSuccess) {
    themeClass = 'status-success';
    iconSvg = `<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
  } else if (isCancelled) {
    themeClass = 'status-cancelled';
    iconSvg = `<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
  } else {
    themeClass = 'status-error';
    iconSvg = `<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`;
  }

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)} - 有案上</title>
  <style>
    :root {
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --text-main: #0f172a;
      --text-sub: #475569;
      --text-muted: #64748b;
      --border: #e2e8f0;
      --btn-bg: #0f172a;
      --btn-text: #ffffff;
      --btn-hover: #1e293b;
      --tip-bg: #f1f5f9;
      --shadow: 0 20px 25px -5px rgba(0,0,0,0.06), 0 8px 10px -6px rgba(0,0,0,0.04);
      --icon-success-bg: #ecfdf5;
      --icon-success-color: #059669;
      --icon-success-ring: #a7f3d0;
      --icon-cancel-bg: #fffbeb;
      --icon-cancel-color: #d97706;
      --icon-cancel-ring: #fde68a;
      --icon-error-bg: #fef2f2;
      --icon-error-color: #dc2626;
      --icon-error-ring: #fecaca;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #090d16;
        --card-bg: #111827;
        --text-main: #f8fafc;
        --text-sub: #94a3b8;
        --text-muted: #64748b;
        --border: #1f2937;
        --btn-bg: #f8fafc;
        --btn-text: #0f172a;
        --btn-hover: #e2e8f0;
        --tip-bg: #1e293b;
        --shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        --icon-success-bg: rgba(5, 150, 105, 0.15);
        --icon-success-color: #34d399;
        --icon-success-ring: rgba(52, 211, 153, 0.3);
        --icon-cancel-bg: rgba(217, 119, 6, 0.15);
        --icon-cancel-color: #fbbf24;
        --icon-cancel-ring: rgba(251, 191, 36, 0.3);
        --icon-error-bg: rgba(220, 38, 38, 0.15);
        --icon-error-color: #f87171;
        --icon-error-ring: rgba(248, 113, 113, 0.3);
      }
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      background: var(--bg);
      color: var(--text-main);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      -webkit-font-smoothing: antialiased;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 40px 36px 36px;
      max-width: 440px;
      width: 100%;
      text-align: center;
      box-shadow: var(--shadow);
      animation: cardIn 0.35s cubic-bezier(0.16, 1, 0.3, 1);
    }
    @keyframes cardIn {
      from { opacity: 0; transform: translateY(14px) scale(0.98); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }
    .icon-badge {
      width: 64px;
      height: 64px;
      border-radius: 50%;
      margin: 0 auto 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      position: relative;
    }
    .icon-badge::after {
      content: '';
      position: absolute;
      inset: -4px;
      border-radius: 50%;
      border: 2px solid transparent;
    }
    .status-success .icon-badge {
      background: var(--icon-success-bg);
      color: var(--icon-success-color);
    }
    .status-success .icon-badge::after { border-color: var(--icon-success-ring); }
    .status-cancelled .icon-badge {
      background: var(--icon-cancel-bg);
      color: var(--icon-cancel-color);
    }
    .status-cancelled .icon-badge::after { border-color: var(--icon-cancel-ring); }
    .status-error .icon-badge {
      background: var(--icon-error-bg);
      color: var(--icon-error-color);
    }
    .status-error .icon-badge::after { border-color: var(--icon-error-ring); }
    .icon-svg { width: 32px; height: 32px; }
    .title {
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -0.01em;
      margin-bottom: 8px;
    }
    .subtitle {
      font-size: 14.5px;
      font-weight: 600;
      color: var(--text-sub);
      margin-bottom: 12px;
    }
    .message {
      font-size: 13.5px;
      line-height: 1.6;
      color: var(--text-muted);
      margin-bottom: 24px;
    }
    .terminal-tip {
      background: var(--tip-bg);
      border-radius: 12px;
      padding: 12px 14px;
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 24px;
      text-align: left;
    }
    .tip-icon { font-size: 16px; flex-shrink: 0; }
    .tip-text { font-size: 12.5px; color: var(--text-sub); font-weight: 500; line-height: 1.4; }
    .btn-close {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      height: 44px;
      border-radius: 12px;
      border: none;
      background: var(--btn-bg);
      color: var(--btn-text);
      font-size: 14.5px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }
    .btn-close:hover {
      background: var(--btn-hover);
      transform: translateY(-1px);
    }
    .btn-close:active { transform: translateY(0); }
    .brand-mark {
      margin-top: 24px;
      font-size: 11.5px;
      color: var(--text-muted);
      opacity: 0.8;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
    }
  </style>
</head>
<body class="${themeClass}">
  <div class="card">
    <div class="icon-badge">
      ${iconSvg}
    </div>
    <h1 class="title">${escapeHtml(title)}</h1>
    <p class="subtitle">${escapeHtml(subtitle)}</p>
    <p class="message">${escapeHtml(message)}</p>
    
    <div class="terminal-tip">
      <span class="tip-icon">💻</span>
      <span class="tip-text">授权状态已同步至本机进程，请回到终端窗口继续下一步操作。</span>
    </div>

    <button id="closeBtn" class="btn-close" type="button" onclick="closeWindow()">
      ${autoCloseSeconds > 0 ? `关闭此页面 (<span id="count">${autoCloseSeconds}</span>s)` : '关闭此页面'}
    </button>

    <div class="brand-mark">
      <span>youanshang · 安全授权中心</span>
    </div>
  </div>

  <script>
    function closeWindow() {
      window.close();
      setTimeout(function() {
        var btn = document.getElementById('closeBtn');
        if (btn) {
          btn.innerText = '按快捷键 Ctrl+W (或 ⌘+W) 关闭窗口';
          btn.style.opacity = '0.8';
        }
      }, 300);
    }
    ${autoCloseSeconds > 0 ? `
    var remaining = ${autoCloseSeconds};
    var timer = setInterval(function() {
      remaining--;
      var el = document.getElementById('count');
      if (el) el.innerText = remaining;
      if (remaining <= 0) {
        clearInterval(timer);
        closeWindow();
      }
    }, 1000);
    ` : ''}
  </script>
</body>
</html>`;
}

async function listenForCallback(config, pending, { timeoutMs = 300000, ready = () => {} } = {}) {
  const redirect = new URL(config.redirect_uri);
  return new Promise((resolve, reject) => {
    let settled = false;
    let timer;
    const finish = (error, code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      process.removeListener('SIGINT', cancel);
      process.removeListener('SIGTERM', cancel);
      server.close();
      server.closeAllConnections();
      error ? reject(error) : resolve(code);
    };
    const cancel = () => finish(new CliError('CANCELLED', '登录已中止'));
    const server = http.createServer((req, res) => {
      res.setHeader('Cache-Control', 'no-store');
      res.setHeader('Referrer-Policy', 'no-referrer');
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      res.setHeader('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; frame-ancestors 'none'");
      if (req.method !== 'GET' || req.headers.host !== redirect.host || !req.url.startsWith('/callback?')) {
        res.writeHead(404);
        res.end(renderCallbackHtml({ status: 'error', title: '未找到回调', subtitle: '404 错误', message: '请求的路径或主机地址无效。' }));
        return;
      }
      try {
        const code = parseCallback(`${redirect.origin}${req.url}`, config, pending);
        res.writeHead(200);
        res.end(renderCallbackHtml({
          status: 'success',
          title: '授权成功',
          subtitle: '已成功接收安全授权凭证',
          message: '请回到终端查看最终登录结果。此页面已完成使命，可以安全关闭。',
          autoCloseSeconds: 5,
        }), () => finish(null, code));
      } catch (error) {
        const isDenied = error.code === 'ACCESS_DENIED';
        res.writeHead(isDenied ? 200 : 400);
        res.end(renderCallbackHtml({
          status: isDenied ? 'cancelled' : 'error',
          title: isDenied ? '已取消授权' : '授权未完成',
          subtitle: isDenied ? '你已主动取消本次应用授权' : '授权回调校验未通过',
          message: error.message || '未能完成本次登录授权。',
        }), () => { if (isDenied) finish(error); });
      }
    });
    server.on('error', () => finish(new CliError('CALLBACK_UNAVAILABLE', '本机回调端口无法使用，请关闭占用程序或使用 login --manual')));
    process.once('SIGINT', cancel);
    process.once('SIGTERM', cancel);
    server.listen(Number(redirect.port), '127.0.0.1', () => {
      timer = setTimeout(() => finish(new CliError('LOGIN_TIMEOUT', '等待授权超时，可用完整回调地址继续或重新发起登录')), timeoutMs);
      ready();
    });
  });
}

function tokenRecord(result) {
  if (!result || typeof result.access_token !== 'string' || !result.access_token
    || typeof result.refresh_token !== 'string' || !result.refresh_token
    || result.token_type !== 'Bearer' || !Number.isFinite(result.expires_in) || result.expires_in <= 0)
    fail('INVALID_RESPONSE', '授权服务返回的凭据格式不正确，请重新登录');
  return { access_token: result.access_token, refresh_token: result.refresh_token,
    expires_at: Date.now() + result.expires_in * 1000 };
}

async function exchange(directory, state, code) {
  const pending = state.pending;
  delete state.pending;
  // 消费标记先落盘，网络异常时不能重放一次性授权码。
  await writeState(directory, state);
  const result = await request(state.config, '/token', { body: {
    client_id: state.config.client_id, code, redirect_uri: state.config.redirect_uri, code_verifier: pending.verifier,
  } });
  state.tokens = tokenRecord(result);
  await writeState(directory, state);
  return { configured: true, authorized: true, expires_at: new Date(state.tokens.expires_at).toISOString() };
}

async function refresh(directory, state) {
  const previous = state.tokens;
  // 刷新操作可能已在服务端成功，即使响应丢失也不重放旧 refresh_token。
  state.refresh_uncertain = true;
  await writeState(directory, state);
  const result = await request(state.config, '/refresh', { body: {
    client_id: state.config.client_id, refresh_token: previous.refresh_token,
  } });
  state.tokens = tokenRecord(result);
  delete state.refresh_uncertain;
  await writeState(directory, state);
}

async function authenticated(directory, state, endpoint, method) {
  if (!state.tokens) fail('AUTH_REQUIRED', '尚未授权，请先执行 login');
  if (state.refresh_uncertain) fail('REFRESH_UNCERTAIN', '上次刷新结果不确定，已停止重放凭据；请 logout，或在网站解绑后清除本地状态');
  const refreshed = state.tokens.expires_at <= Date.now() + 30000;
  if (refreshed) await refresh(directory, state);
  try { return await request(state.config, endpoint, { method, token: state.tokens.access_token }); }
  catch (error) {
    if (error.status !== 401 || refreshed) throw error;
    await refresh(directory, state);
    return request(state.config, endpoint, { method, token: state.tokens.access_token });
  }
}

async function authenticatedSkill(directory, state, method, endpoint, body) {
  if (!state.tokens) fail('AUTH_REQUIRED', '尚未授权，请先执行 login');
  if (state.refresh_uncertain) fail('REFRESH_UNCERTAIN', '上次刷新结果不确定，已停止重放凭据；请 logout，或在网站解绑后清除本地状态');
  const refreshed = state.tokens.expires_at <= Date.now() + 30000;
  if (refreshed) await refresh(directory, state);
  const baseUrl = state.config.skill_base_url;
  if (!baseUrl) fail('INVALID_CONFIG', '本服务暂未开通业务接口，请等待新版 skill 或联系管理员');
  try { return await request(state.config, endpoint, { method, token: state.tokens.access_token, body, baseUrl }); }
  catch (error) {
    if (error.status !== 401 || refreshed) throw error;
    await refresh(directory, state);
    return request(state.config, endpoint, { method, token: state.tokens.access_token, body, baseUrl });
  }
}

async function run(command, options = {}, emit = () => {}) {
  const directory = await configDirectory(options);
  return withLock(directory, async state => {
    if (!state.config) {
      state.config = validateConfig(runtime);
      await writeState(directory, state);
    }
    if (command === 'configure') {
      if (state.tokens || state.pending) fail('ACTIVE_SESSION', '请先退出已有授权或完成/取消待授权会话，再更改服务配置');
      state.config = validateConfig({ api_base_url: options['api-base-url'], authorize_url: options['authorize-url'],
        client_id: options['client-id'], redirect_uri: options['redirect-uri'] || 'http://127.0.0.1:17888/callback',
        scopes: (options.scope || 'profile:read').split(/\s+/) });
      await writeState(directory, state);
      return { configured: true, ...state.config };
    }
    if (command === 'status') return { configured: Boolean(state.config), authorized: Boolean(state.tokens),
      pending_login: Boolean(state.pending), refresh_uncertain: Boolean(state.refresh_uncertain),
      expires_at: state.tokens ? new Date(state.tokens.expires_at).toISOString() : null };
    state.config = validateConfig(state.config);
    if (command === 'cancel-login') {
      delete state.pending;
      await writeState(directory, state);
      return { cancelled: true };
    }
    if (command === 'login') {
      if (state.tokens) {
        try {
          await request(state.config, '/check', { token: state.tokens.access_token });
          return { authorized: true, already_authorized: true };
        } catch (error) {
          if (error.status !== 401) throw error;
          // 先尝试刷新；仅已被服务端明确拒绝的凭据才清除。
          try {
            if (state.refresh_uncertain) throw error;
            await refresh(directory, state);
            return { authorized: true, already_authorized: true };
          } catch (refreshError) {
            if (refreshError.status !== 401) throw refreshError;
            delete state.tokens;
            delete state.refresh_uncertain;
            await writeState(directory, state);
          }
        }
      }
      if (options.token) return exchange(directory, state, manualCode(options.token, state.pending));
      if (options['callback-url']) {
        let code;
        try { code = parseCallback(options['callback-url'], state.config, state.pending); }
        catch (error) {
          if (error.code === 'ACCESS_DENIED') { delete state.pending; await writeState(directory, state); }
          throw error;
        }
        return exchange(directory, state, code);
      }
      const login = pendingLogin(state.config);
      state.pending = login.pending;
      await writeState(directory, state);
      const notify = () => emit({ type: 'authorization', code: 0, url: login.url, data: { authorize_url: login.url }, expires_in: 600,
        msg: '请本人打开链接，核对应用和权限后确认；不要把站内密码交给 CLI' });
      if (options.manual) { notify(); return { pending: true, authorize_url: login.url, msg: require('./messages.cjs').fallback }; }
      notify();
      try {
        const code = await listenForCallback(state.config, state.pending, { ready: () => {
          if (!options['no-browser']) openBrowser(login.url);
        } });
        return await exchange(directory, state, code);
      } catch (error) {
        if (['ACCESS_DENIED', 'CANCELLED'].includes(error.code)) { delete state.pending; await writeState(directory, state); }
        else if (state.pending) error.data = { authorize_url: login.url, fallback: require('./messages.cjs').fallback };
        throw error;
      }
    }
    if (command === 'check') return authenticated(directory, state, '/check', 'POST');
    if (command === 'profile' || command === 'get-user-info') return authenticated(directory, state, '/profile', 'GET');
    if (command === 'unauthorize') {
      const ticket = await authenticated(directory, state, '/unauthorize', 'POST');
      const url = new URL(state.config.authorize_url);
      url.pathname = url.pathname.replace(/\/authorize\/?$/, '/revoke');
      url.search = '';
      url.hash = '';
      url.searchParams.set('ticket', ticket.ticket);
      return { revokeUrl: url.href, expires_in: ticket.expires_in,
        msg: '请本人打开解除授权页面，登录同一账号并确认。打开链接不会自动解绑，确认后仅当前设备授权失效。' };
    }
    if (command === 'logout') {
      if (state.tokens && !options['local-only']) {
        // 注销端点可用签名有效的过期 token 撤销所属会话，不刷新、不重放 refresh_token。
        await request(state.config, '/logout', { token: state.tokens.access_token });
      }
      delete state.tokens;
      delete state.pending;
      delete state.refresh_uncertain;
      await writeState(directory, state);
      return { authorized: false, remote_revocation_confirmed: !options['local-only'], msg: options['local-only']
        ? '仅清除了本地登录态；未确认服务端撤销，请在网站的应用授权管理中解绑'
        : '当前设备已退出，其他设备和账号数据不受影响' };
    }
    fail('UNKNOWN_COMMAND', '未知命令，请使用 --help');
  });
}

module.exports = { CliError, run, trustedUrl, validateConfig, pendingLogin, parseCallback, listenForCallback,
  withLock, readState, writeState, request, authenticatedSkill, challenge, defaultDirectory, configDirectory, manualCode };

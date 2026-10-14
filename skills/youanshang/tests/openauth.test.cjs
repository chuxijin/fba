'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const { execFileSync } = require('node:child_process');
const { run, validateConfig, pendingLogin, parseCallback, listenForCallback, readState, writeState, challenge, defaultDirectory } = require('../lib/openauth.cjs');

const base = { api_base_url: 'http://127.0.0.1:8000/api/v1/openauth', authorize_url: 'http://localhost:3000/openauth/authorize',
  client_id: 'test-cli', redirect_uri: 'http://127.0.0.1:17888/callback', scopes: ['profile:read'] };

async function temporary(t) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'youanshang-cli-test-'));
  t.after(async () => {
    const actual = await fs.realpath(root);
    assert.equal(path.dirname(actual).toLowerCase(), (await fs.realpath(os.tmpdir())).toLowerCase());
    assert.ok(path.basename(actual).startsWith('youanshang-cli-test-'));
    await fs.rm(actual, { recursive: true, force: true });
  });
  return root;
}

async function apiServer(t, handler) {
  const server = http.createServer(async (req, res) => {
    let raw = '';
    for await (const chunk of req) raw += chunk;
    try { await handler(req, res, raw ? JSON.parse(raw) : null); }
    catch { res.writeHead(500); res.end('{}'); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => { server.closeAllConnections(); return new Promise(resolve => server.close(resolve)); });
  return `http://127.0.0.1:${server.address().port}`;
}

function reply(res, data, status = 200) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ code: status, data }));
}

async function fixture(t) {
  const directory = await temporary(t);
  const seen = { refreshes: 0, logouts: 0, exchanges: 0, profileCalls: 0 };
  const api = await apiServer(t, async (req, res, body) => {
    if (req.url === '/token') {
      seen.exchanges++;
      assert.equal(challenge(body.code_verifier), seen.challenge);
      assert.equal(body.client_id, 'test-cli');
      assert.equal('client_secret' in body, false);
      reply(res, { access_token: 'fake-access1', refresh_token: 'fake-refresh1', token_type: 'Bearer', expires_in: 7200 });
    } else if (req.url === '/refresh') {
      seen.refreshes++;
      assert.equal(body.refresh_token, 'fake-refresh1');
      await new Promise(resolve => setTimeout(resolve, 60));
      reply(res, { access_token: 'fake-access2', refresh_token: 'fake-refresh2', token_type: 'Bearer', expires_in: 7200 });
    } else if (req.url === '/profile') {
      seen.profileCalls++;
      assert.match(req.headers.authorization, /^Bearer fake-access[12]$/);
      reply(res, { user_id: 123, nickname: '测试账号', avatar: null });
    } else if (req.url === '/logout') { seen.logouts++; reply(res, null); }
    else reply(res, null, 404);
  });
  const options = { 'config-dir': directory };
  await run('configure', { ...options, 'api-base-url': api, 'authorize-url': base.authorize_url, 'client-id': base.client_id });
  const events = [];
  await run('login', { ...options, manual: true }, event => events.push(event));
  const url = new URL(events[0].url);
  seen.challenge = url.searchParams.get('code_challenge');
  const callback = `${base.redirect_uri}?code=${'c'.repeat(32)}&state=${url.searchParams.get('state')}`;
  const login = await run('login', { ...options, 'callback-url': callback });
  assert.equal(login.authorized, true);
  return { directory, options, seen, events, login };
}

test('PKCE matches RFC7636 vector', () => {
  assert.equal(challenge('dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk'), 'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM');
});

test('renamed skill uses new storage and preserves legacy sessions without copying', async t => {
  const root = await temporary(t);
  const preferred = path.join(root, 'youanshang-skill');
  const legacy = path.join(root, 'gongkao-skill');
  assert.equal(await defaultDirectory(root), preferred);
  await fs.mkdir(legacy);
  assert.equal(await defaultDirectory(root), legacy);
  await fs.mkdir(preferred);
  assert.equal(await defaultDirectory(root), preferred);
});

test('only HTTPS or explicit local HTTP is allowed', () => {
  assert.equal(validateConfig(base).client_id, 'test-cli');
  for (const url of ['http://public.example/openauth', 'https://user:password@example.com', 'https://example.com?secret=1', 'file:///tmp', 'https://example.com/#bad'])
    assert.throws(() => validateConfig({ ...base, api_base_url: url }));
  assert.throws(() => validateConfig({ ...base, redirect_uri: 'http://localhost:17888/callback' }));
});

test('callback validates address, state, duplicates, expiry and cancellation', () => {
  const { pending } = pendingLogin(base);
  const valid = `${base.redirect_uri}?code=${'c'.repeat(32)}&state=${pending.state}`;
  assert.equal(parseCallback(valid, base, pending), 'c'.repeat(32));
  for (const value of [valid.replace('127.0.0.1', 'evil.example'), valid + '&code=duplicate', valid + '&state=duplicate',
    valid.replace(pending.state, 'wrong'), valid + '#fragment', 'only-a-code'])
    assert.throws(() => parseCallback(value, base, pending));
  assert.throws(() => parseCallback(valid, base, pending, pending.created_at + 600001), { code: 'LOGIN_EXPIRED' });
  assert.throws(() => parseCallback(`${base.redirect_uri}?error=access_denied&state=${pending.state}`, base, pending), { code: 'ACCESS_DENIED' });
});

test('manual login, profile and logout never output credentials', async t => {
  const env = await fixture(t);
  const profile = await run('profile', env.options);
  assert.equal(profile.nickname, '测试账号');
  const state = await readState(env.directory);
  assert.equal(state.pending, undefined);
  const publicOutput = JSON.stringify([env.login, env.events, profile, await run('status', env.options)]);
  assert.equal(publicOutput.includes('fake-access'), false);
  assert.equal(publicOutput.includes('fake-refresh'), false);
  const logout = await run('logout', env.options);
  assert.equal(logout.remote_revocation_confirmed, true);
  assert.equal(env.seen.logouts, 1);
  assert.equal((await readState(env.directory)).tokens, undefined);
});

test('concurrent commands rotate a refresh token exactly once', async t => {
  const env = await fixture(t);
  const state = await readState(env.directory);
  state.tokens.expires_at = 1;
  await writeState(env.directory, state);
  const results = await Promise.all([run('profile', env.options), run('profile', env.options)]);
  assert.equal(results.length, 2);
  assert.equal(env.seen.refreshes, 1);
  assert.equal((await readState(env.directory)).tokens.refresh_token, 'fake-refresh2');
});

test('network response loss marks refresh uncertain and never replays it', async t => {
  const directory = await temporary(t);
  let calls = 0;
  const api = await apiServer(t, (req, res) => { calls++; req.socket.destroy(); });
  const options = { 'config-dir': directory };
  await run('configure', { ...options, 'api-base-url': api, 'authorize-url': base.authorize_url, 'client-id': 'test' });
  const state = await readState(directory);
  state.tokens = { access_token: 'old-access', refresh_token: 'old-refresh', expires_at: 1 };
  await writeState(directory, state);
  await assert.rejects(run('profile', options), { code: 'NETWORK_ERROR' });
  await assert.rejects(run('profile', options), { code: 'REFRESH_UNCERTAIN' });
  assert.equal(calls, 1);
  assert.equal((await readState(directory)).refresh_uncertain, true);
  assert.equal((await run('logout', { ...options, 'local-only': true })).remote_revocation_confirmed, false);
});

test('an active account cannot be silently pointed at another API', async t => {
  const env = await fixture(t);
  await assert.rejects(run('configure', { ...env.options, 'api-base-url': 'https://evil.example' }), { code: 'ACTIVE_SESSION' });
});

test('local listener rejects wrong state, then accepts one valid callback', async t => {
  const reservation = http.createServer();
  await new Promise(resolve => reservation.listen(0, '127.0.0.1', resolve));
  const port = reservation.address().port;
  await new Promise(resolve => reservation.close(resolve));
  const config = { ...base, redirect_uri: `http://127.0.0.1:${port}/callback` };
  const { pending } = pendingLogin(config);
  let signal;
  const ready = new Promise(resolve => { signal = resolve; });
  const result = listenForCallback(config, pending, { timeoutMs: 4000, ready: signal });
  await ready;
  const bad = await fetch(`${config.redirect_uri}?code=${'c'.repeat(32)}&state=wrong`);
  assert.equal(bad.status, 400);
  assert.equal(bad.headers.get('referrer-policy'), 'no-referrer');
  const good = await fetch(`${config.redirect_uri}?code=${'c'.repeat(32)}&state=${pending.state}`);
  assert.equal(good.status, 200);
  await good.text();
  assert.equal(await result, 'c'.repeat(32));
});

test('invalid arguments do not echo raw values', () => {
  try {
    execFileSync(process.execPath, [path.resolve(__dirname, '../scripts/youanshang.cjs'), 'check', '--token', 'TOP-SECRET'], { encoding: 'utf8' });
    assert.fail('expected failure');
  } catch (error) {
    assert.equal(error.stdout.includes('TOP-SECRET'), false);
    assert.equal(JSON.parse(error.stdout).code, -1);
    assert.equal(JSON.parse(error.stdout).reason, 'INVALID_ARGUMENT');
  }
});

test('installer copies only runtime files and refuses implicit overwrite', async t => {
  const destination = await temporary(t);
  const script = path.resolve(__dirname, '../scripts/install.cjs');
  const configDir = path.join(destination, 'isolated-config');
  const output = execFileSync(process.execPath, [script, '--destination', destination, '--config-dir', configDir], { encoding: 'utf8' });
  const result = output.split(/\r?\n/).filter(line => line.startsWith('{')).map(JSON.parse).find(row => row.type === 'result');
  assert.equal(result.data.files, 15);
  assert.equal((await fs.readdir(path.join(destination, 'youanshang'))).includes('tests'), false);
  assert.throws(() => execFileSync(process.execPath, [script, '--destination', destination, '--config-dir', configDir], { stdio: 'pipe' }));
  assert.match(execFileSync(process.execPath, [path.join(destination, 'youanshang/scripts/youanshang.cjs'), '--help'], { encoding: 'utf8' }), /profile/);
});

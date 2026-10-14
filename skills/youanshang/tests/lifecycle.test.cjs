'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const { execFile } = require('node:child_process');
const { promisify } = require('node:util');
const exec = promisify(execFile);
const { FILES, hash, extractVerified, matches, installFiles } = require('../lib/package.cjs');
const { run, manualCode, pendingLogin, readState, writeState } = require('../lib/openauth.cjs');
const config = require('../runtime.json');
const source = path.resolve(__dirname, '..');

async function temp(t) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'youanshang-lifecycle-'));
  t.after(async () => {
    const actual = await fs.realpath(root);
    assert.equal(path.dirname(actual).toLowerCase(), (await fs.realpath(os.tmpdir())).toLowerCase());
    assert.ok(path.basename(actual).startsWith('youanshang-lifecycle-'));
    await fs.rm(actual, { recursive: true, force: true });
  });
  return root;
}

function storedZip(files) {
  const bodies = [], directory = [];
  let offset = 0;
  for (const [name, bytes] of files) {
    const filename = Buffer.from(`youanshang/${name}`);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50);
    local.writeUInt32LE(bytes.length, 18);
    local.writeUInt32LE(bytes.length, 22);
    local.writeUInt16LE(filename.length, 26);
    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50);
    central.writeUInt32LE(bytes.length, 20);
    central.writeUInt32LE(bytes.length, 24);
    central.writeUInt16LE(filename.length, 28);
    central.writeUInt32LE(offset, 42);
    bodies.push(local, filename, bytes);
    directory.push(central, filename);
    offset += local.length + filename.length + bytes.length;
  }
  const central = Buffer.concat(directory);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50);
  end.writeUInt16LE(files.size, 8);
  end.writeUInt16LE(files.size, 10);
  end.writeUInt32LE(central.length, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...bodies, central, end]);
}

async function fixture(t) {
  const root = await temp(t);
  const install = path.join(root, 'youanshang');
  const account = path.join(root, 'account');
  await fs.mkdir(install);
  let zip, release;
  let corrupt = false;
  const counts = { downloads: 0, logout: 0 };
  const server = http.createServer((req, res) => {
    res.setHeader('Content-Type', 'application/json');
    if (req.url === '/skill-config') res.end(JSON.stringify({ code: 200, data: release }));
    else if (req.url === '/skill-package') { counts.downloads++; res.end(corrupt ? Buffer.from('broken') : zip); }
    else if (req.url === '/logout') { counts.logout++; res.end(JSON.stringify({ code: 200, data: null })); }
    else { res.writeHead(404); res.end('{}'); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => { server.closeAllConnections(); return new Promise(resolve => server.close(resolve)); });
  const files = new Map();
  for (const name of FILES) {
    const data = name === 'runtime.json'
      ? Buffer.from(JSON.stringify({ ...config, api_base_url: `http://127.0.0.1:${server.address().port}` }))
      : await fs.readFile(path.join(source, name));
    files.set(name, data);
    await fs.mkdir(path.dirname(path.join(install, name)), { recursive: true });
    await fs.writeFile(path.join(install, name), data);
  }
  zip = storedZip(files);
  release = { version: config.version, sha256: hash(zip), package_path: 'skill-package',
    files: Object.fromEntries([...files].map(([name, bytes]) => [name, hash(bytes)])) };
  async function execute(script, ...args) {
    const result = await exec(process.execPath, [path.join(install, `scripts/${script}.cjs`), ...args, '--config-dir', account],
      { encoding: 'utf8', windowsHide: true });
    return result.stdout.split(/\r?\n/).filter(line => line.startsWith('{')).map(JSON.parse);
  }
  return { root, install, account, files, zip, release, counts, execute, corrupt: () => { corrupt = true; } };
}

test('manual authorization code requires pending PKCE and validates format/expiry', () => {
  const { pending } = pendingLogin(config);
  assert.equal(manualCode('a'.repeat(43), pending), 'a'.repeat(43));
  assert.throws(() => manualCode('a'.repeat(43), null), { code: 'LOGIN_EXPIRED' });
  assert.throws(() => manualCode('a'.repeat(43), pending, pending.created_at + 600001), { code: 'LOGIN_EXPIRED' });
  assert.throws(() => manualCode('bad code', pending), { code: 'INVALID_CALLBACK' });
});

test('fresh CLI is preconfigured and session parameters are not echoed', async t => {
  const root = await temp(t);
  const result = await exec(process.execPath, [path.join(source, 'scripts/youanshang.cjs'), 'status',
    '--session-input', 'PRIVATE-QUESTION-CONTENT', '--session-id', '1784035443-a1b2c3', '--config-dir', root]);
  const status = JSON.parse(result.stdout);
  assert.equal(status.code, 0);
  assert.equal(status.data.configured, true);
  assert.equal(result.stdout.includes('PRIVATE-QUESTION'), false);
  assert.equal((await fs.readFile(path.join(root, 'state.json'), 'utf8')).includes('PRIVATE-QUESTION'), false);
});

test('full install repairs docs, skips unchanged package, welcomes only once and preserves login', async t => {
  const f = await fixture(t);
  await fs.writeFile(path.join(f.install, 'SKILL.md'), 'old documentation');
  const first = await f.execute('install');
  assert.equal(first.find(row => row.type === 'result').code, 0);
  assert.equal(first.filter(row => row.type === 'welcome').length, 1);
  assert.equal(f.counts.downloads, 1);
  assert.equal(await matches(f.install, f.release), true);
  const state = await readState(f.account);
  state.tokens = { access_token: 'private-access', refresh_token: 'private-refresh', expires_at: 1 };
  await writeState(f.account, state);
  const second = await f.execute('install');
  assert.equal(second.filter(row => row.type === 'welcome').length, 0);
  assert.equal(f.counts.downloads, 1);
  assert.equal((await readState(f.account)).tokens.access_token, 'private-access');
});

test('invalid archive cannot change installed files or credentials', async t => {
  const f = await fixture(t);
  await f.execute('install');
  const previous = await fs.readFile(path.join(f.install, 'SKILL.md'));
  f.corrupt();
  await assert.rejects(f.execute('install', '--force'));
  assert.deepEqual(await fs.readFile(path.join(f.install, 'SKILL.md')), previous);
  const badFiles = new Map(f.files);
  badFiles.set('../escape.txt', badFiles.get('SKILL.md'));
  badFiles.delete('SKILL.md');
  const zip = storedZip(badFiles);
  assert.throws(() => extractVerified(zip, { ...f.release, sha256: hash(zip) }), { code: 'INVALID_PACKAGE' });
  // 未来新增业务文档也能通过完整包升级，而不是被固定文件数量锁死。
  const expanded = new Map(f.files);
  expanded.set('references/practice.md', Buffer.from('Future documented capability'));
  const futureZip = storedZip(expanded);
  const futureRelease = { ...f.release, sha256: hash(futureZip),
    files: Object.fromEntries([...expanded].map(([name, bytes]) => [name, hash(bytes)])) };
  await installFiles(f.install, extractVerified(futureZip, futureRelease));
  assert.equal(await matches(f.install, futureRelease), true);
});

test('uninstall revokes signed expired session without refreshing and keeps skill/foreign files', async t => {
  const f = await fixture(t);
  await f.execute('install');
  const state = await readState(f.account);
  state.tokens = { access_token: 'expired-access', refresh_token: 'do-not-replay', expires_at: 1 };
  await writeState(f.account, state);
  await fs.writeFile(path.join(f.account, 'keep.txt'), 'user owned');
  assert.equal((await f.execute('uninstall'))[0].code, 0);
  assert.equal(f.counts.logout, 1);
  await assert.rejects(fs.access(path.join(f.account, 'state.json')));
  assert.equal(await fs.readFile(path.join(f.account, 'keep.txt'), 'utf8'), 'user owned');
  await fs.access(path.join(f.install, 'SKILL.md'));
});

test('uninstall failure preserves credentials and reports failure', async t => {
  const f = await fixture(t);
  await f.execute('install');
  const state = await readState(f.account);
  state.config.api_base_url += '/missing';
  state.tokens = { access_token: 'private-access', refresh_token: 'private-refresh', expires_at: 1 };
  await writeState(f.account, state);
  await assert.rejects(f.execute('uninstall'));
  assert.equal((await readState(f.account)).tokens.access_token, 'private-access');
});

test('unauthorize only returns confirmation link, does not logout', async t => {
  const root = await temp(t);
  const calls = [];
  const server = http.createServer((req, res) => {
    calls.push(req.url);
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify({ code: 200, data: { ticket: 't'.repeat(43), expires_in: 600 } }));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  await run('status', { 'config-dir': root });
  const state = await readState(root);
  state.config.api_base_url = `http://127.0.0.1:${server.address().port}`;
  state.tokens = { access_token: 'test-access', refresh_token: 'test-refresh', expires_at: Date.now() + 120000 };
  await writeState(root, state);
  const result = await run('unauthorize', { 'config-dir': root });
  assert.match(result.revokeUrl, /\/openauth\/revoke\?ticket=/);
  assert.deepEqual(calls, ['/unauthorize']);
  assert.equal((await readState(root)).tokens.access_token, 'test-access');
});

'use strict';
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const zlib = require('node:zlib');
const { CliError, trustedUrl } = require('./openauth.cjs');

const FILES = ['SKILL.md', 'runtime.json', 'references/auth.md', 'references/calculation.md', 'references/qbank.md',
  'lib/openauth.cjs', 'lib/messages.cjs', 'lib/package.cjs', 'lib/commands/calculation.cjs', 'lib/commands/qbank.cjs',
  'scripts/youanshang.cjs', 'scripts/install.cjs', 'scripts/install.sh',
  'scripts/uninstall.cjs', 'scripts/uninstall.sh'];
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const invalid = () => { throw new CliError('INVALID_PACKAGE', '安装包或校验清单不合法，未安装未校验文件'); };
const allowedName = name => ['SKILL.md', 'runtime.json'].includes(name)
  || /^(?:lib\/(?:commands\/)?[a-z0-9_-]+\.cjs|scripts\/[a-z0-9_-]+\.(?:cjs|sh)|references\/[a-z0-9_-]+\.md)$/.test(name);

async function fetchBytes(url, limit) {
  trustedUrl(url);
  let response;
  try { response = await fetch(url, { redirect: 'error', signal: AbortSignal.timeout(30000) }); }
  catch { throw new CliError('INSTALL_NETWORK', '无法连接本地安装服务，请启动后端后重试'); }
  if (!response.ok || Number(response.headers.get('content-length')) > limit) invalid();
  const chunks = [];
  let size = 0;
  const reader = response.body.getReader();
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.length;
      if (size > limit) { await reader.cancel(); invalid(); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  return Buffer.concat(chunks);
}

function validateRelease(release) {
  if (!release || !/^\d+\.\d+\.\d+$/.test(release.version) || !/^[a-f0-9]{64}$/.test(release.sha256)
    || release.package_path !== 'skill-package' || !release.files || Array.isArray(release.files)
    || Object.keys(release.files).length > 64) invalid();
  for (const name of FILES) if (!(name in release.files)) invalid();
  for (const [name, digest] of Object.entries(release.files))
    if (!allowedName(name) || !/^[a-f0-9]{64}$/.test(digest)) invalid();
  return release;
}

function extractVerified(zip, release) {
  validateRelease(release);
  if (hash(zip) !== release.sha256 || zip.length < 22 || zip.length > 8 * 1024 * 1024) invalid();
  // 只接受本分发器生成的普通 ZIP：无 ZIP64、加密、多磁盘、目录项或符号链接。
  try {
    const end = zip.length - 22;
    const names = Object.keys(release.files);
    if (zip.readUInt32LE(end) !== 0x06054b50 || zip.readUInt16LE(end + 20) !== 0
      || zip.readUInt32LE(end + 4) !== 0 || zip.readUInt16LE(end + 8) !== names.length
      || zip.readUInt16LE(end + 10) !== names.length) invalid();
    let cursor = zip.readUInt32LE(end + 16);
    if (cursor + zip.readUInt32LE(end + 12) !== end) invalid();
    const centralStart = cursor;
    const result = new Map();
    for (let index = 0; index < names.length; index++) {
      if (zip.readUInt32LE(cursor) !== 0x02014b50) invalid();
      const flags = zip.readUInt16LE(cursor + 8);
      const method = zip.readUInt16LE(cursor + 10);
      const packed = zip.readUInt32LE(cursor + 20);
      const size = zip.readUInt32LE(cursor + 24);
      const nameLength = zip.readUInt16LE(cursor + 28);
      const extra = zip.readUInt16LE(cursor + 30);
      const comment = zip.readUInt16LE(cursor + 32);
      const mode = zip.readUInt32LE(cursor + 38) >>> 16;
      const local = zip.readUInt32LE(cursor + 42);
      const name = zip.subarray(cursor + 46, cursor + 46 + nameLength).toString('utf8');
      const relative = name.replace(/^youanshang\//, '');
      if (name !== `youanshang/${relative}` || !names.includes(relative) || result.has(relative)
        || flags & ~0x800 || ![0, 8].includes(method) || (mode & 0xf000) === 0xa000
        || size > 2 * 1024 * 1024 || local >= centralStart || zip.readUInt32LE(local) !== 0x04034b50) invalid();
      const localNameLength = zip.readUInt16LE(local + 26);
      const localExtra = zip.readUInt16LE(local + 28);
      const start = local + 30 + localNameLength + localExtra;
      if (zip.subarray(local + 30, local + 30 + localNameLength).toString('utf8') !== name
        || zip.readUInt16LE(local + 8) !== method || start + packed > centralStart) invalid();
      const compressed = zip.subarray(start, start + packed);
      const data = method === 0 ? compressed : zlib.inflateRawSync(compressed, { maxOutputLength: 2 * 1024 * 1024 });
      if (data.length !== size || hash(data) !== release.files[relative]) invalid();
      result.set(relative, data);
      cursor += 46 + nameLength + extra + comment;
    }
    if (cursor !== end || JSON.parse(result.get('runtime.json')).version !== release.version) invalid();
    return result;
  } catch (error) { if (error instanceof CliError) throw error; invalid(); }
}

async function safeTarget(root, name) {
  if (!allowedName(name)) invalid();
  const target = path.resolve(root, name);
  if (!target.startsWith(path.resolve(root) + path.sep)) invalid();
  let cursor = path.resolve(root);
  const rootStat = await fs.lstat(cursor);
  if (!rootStat.isDirectory() || rootStat.isSymbolicLink()) invalid();
  const segments = name.split('/');
  for (let i = 0; i < segments.length; i++) {
    cursor = path.join(cursor, segments[i]);
    try {
      const stat = await fs.lstat(cursor);
      if (stat.isSymbolicLink() || (i === segments.length - 1 ? !stat.isFile() : !stat.isDirectory())) invalid();
    } catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  return target;
}

async function matches(root, release) {
  for (const name of Object.keys(release.files)) {
    const target = await safeTarget(root, name);
    try { if (hash(await fs.readFile(target)) !== release.files[name]) return false; }
    catch (error) { if (error.code === 'ENOENT') return false; throw error; }
  }
  return true;
}

async function installFiles(root, files) {
  const backups = new Map();
  const installed = [];
  // 写入前检查所有目标。仅修改白名单文件，既不递归删除目录，也不触碰 credentials/tests。
  for (const name of files.keys()) {
    const target = await safeTarget(root, name);
    try { backups.set(name, await fs.readFile(target)); }
    catch (error) { if (error.code !== 'ENOENT') throw error; backups.set(name, null); }
  }
  async function atomic(name, bytes) {
    const target = await safeTarget(root, name);
    await fs.mkdir(path.dirname(target), { recursive: true });
    const temporary = `${target}.${crypto.randomBytes(8).toString('hex')}.tmp`;
    try {
      await fs.writeFile(temporary, bytes, { flag: 'wx', mode: 0o600 });
      await fs.rename(temporary, target);
    } finally { await fs.rm(temporary, { force: true }); }
  }
  try {
    for (const name of files.keys()) { await atomic(name, files.get(name)); installed.push(name); }
  } catch (error) {
    for (const name of installed.reverse()) {
      if (backups.get(name) === null) await fs.unlink(await safeTarget(root, name));
      else await atomic(name, backups.get(name));
    }
    throw error;
  }
}

module.exports = { FILES, hash, fetchBytes, validateRelease, extractVerified, safeTarget, matches, installFiles };

import assert from 'node:assert/strict'
import test from 'node:test'
import { importTypeScript } from './helpers/typescript.mjs'

const auth = await importTypeScript(new URL('../src/utils/auth.ts', import.meta.url))
const bridge = await importTypeScript(new URL('../src/utils/auth-bridge.ts', import.meta.url))
const { isTrustedSite } = await importTypeScript(new URL('../src/utils/auth-protocol.ts', import.meta.url))
function environment() {
  const data = {}
  globalThis.chrome = { storage: { local: {
    async get() { return { ...data } },
    async set(values) { Object.assign(data, values) },
    async remove(keys) { for (const key of keys) delete data[key] },
  } }, tabs: { async query() { return [] } }, scripting: { async executeScript() { throw new Error('unexpected injection') } } }
  return data
}
const user = { id: 7, nickname: '官网用户', avatar: 'avatar.png' }
function response(data, code = 200) { return new Response(JSON.stringify({ code, data }), { status: code }) }
const tick = () => new Promise((resolve) => setImmediate(resolve))

test('官网桥接仅允许本地官网准确域名和端口', () => {
  for (const site of ['http://localhost:3000/', 'http://127.0.0.1:3000/profile']) assert.ok(isTrustedSite(site))
  for (const site of ['http://localhost:8000/', 'https://localhost:3000/', 'http://localhost.evil:3000/', 'https://fenbi.com/', 'invalid'])
    assert.equal(isTrustedSite(site), false)
})
test('官网登录经后端验证后同步扩展，返回的会话不泄露 refresh token', async () => {
  const data = environment()
  globalThis.fetch = async () => response(user)
  const result = await bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken: 'site-token' })
  assert.equal(data.fba_auth_token.access_token, 'site-token')
  assert.equal(result.user.nickname, '官网用户')
  const publicState = bridge.publicSession({ ...result, token: { ...result.token, refresh_token: 'secret' } })
  assert.equal(publicState.token.refresh_token, undefined)
})
test('扩展退出先清本地并调用服务端撤销；旧官网退出不清除新账号', async () => {
  const data = environment()
  await auth.saveAuthSession({ access_token: 'extension-token' }, user)
  const calls = []
  globalThis.fetch = async (url, options) => {
    assert.equal(data.fba_auth_token, undefined)
    calls.push([url, options.headers.Authorization])
    return response(null)
  }
  await bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGOUT', expectedToken: 'other-token' })
  assert.equal(data.fba_auth_token.access_token, 'extension-token')
  assert.equal(calls.length, 0)
  await bridge.logoutExtension('extension-token')
  assert.equal(data.fba_auth_token, undefined)
  assert.equal(calls[0][1], 'Bearer extension-token')
  assert.match(calls[0][0], /auth\/logout$/)
})
test('撤销/过期会话不继续显示；网络失败保留当前登录', async () => {
  const data = environment()
  await auth.saveAuthSession({ access_token: 'old' }, user)
  globalThis.fetch = async () => { throw new Error('offline') }
  await assert.rejects(bridge.handleSiteAuth({ type: 'SITE_AUTH_GET' }), /offline/)
  assert.equal(data.fba_auth_token.access_token, 'old')
  globalThis.fetch = async () => response(null, 401)
  const result = await bridge.handleSiteAuth({ type: 'SITE_AUTH_GET' })
  assert.equal(result.token, null)
  assert.equal(result.rejectedToken, 'old')
})
test('迟到的官网验证不会覆盖刚在扩展登录的新账号', async () => {
  const data = environment()
  let finish
  globalThis.fetch = async () => new Promise((resolve) => { finish = resolve })
  const pending = bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken: 'site-token' })
  await tick()
  await auth.saveAuthSession({ access_token: 'new-token' }, { id: 8, nickname: '新用户' })
  finish(response(user))
  await pending
  assert.equal(data.fba_auth_token.access_token, 'new-token')
})

test('官网标签页关闭后仍可用现有 Cookie 建立登录，显式退出不自动复活', async () => {
  const data = environment()
  const calls = []
  globalThis.fetch = async (url, options) => {
    calls.push([url, options])
    return url.endsWith('/api/extension/session')
      ? response({ token: { access_token: 'cookie-token' }, user }) : response(user)
  }
  await bridge.bootstrapSiteSession()
  assert.equal(data.fba_auth_token.access_token, 'cookie-token')
  assert.equal(calls[0][1].credentials, 'include')
  data.fba_auth_token = undefined
  data.fba_auth_signed_out = true
  await bridge.bootstrapSiteSession()
  assert.equal(calls.length, 2)
})

test('官网验证途中退出不会被迟到的登录重新激活', async () => {
  const data = environment()
  let finish
  globalThis.fetch = async () => new Promise((resolve) => { finish = resolve })
  const pending = bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken: 'site-token' })
  await tick()
  await bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGOUT', expectedToken: 'site-token' })
  finish(response(user))
  await pending
  assert.equal(data.fba_auth_token, undefined)
})

test('退出后不恢复旧 Cookie，但官网重新登录的新 Cookie 可以同步', async () => {
  const data = environment()
  await auth.saveAuthSession({ access_token: 'old-cookie' }, user)
  globalThis.fetch = async () => response(null)
  await bridge.logoutExtension('old-cookie')
  assert.equal(data.fba_auth_signed_out, true)
  assert.equal(data.fba_auth_signed_out_token, await auth.getTokenFingerprint('old-cookie'))

  let websiteToken = 'old-cookie'
  let validations = 0
  globalThis.fetch = async (url) => {
    if (url.endsWith('/api/extension/session')) return response({ token: { access_token: websiteToken } })
    validations++
    return response(user)
  }
  await bridge.bootstrapSiteSession()
  assert.equal(data.fba_auth_token, undefined)
  assert.equal(validations, 0)
  websiteToken = 'new-cookie'
  await bridge.bootstrapSiteSession()
  assert.equal(data.fba_auth_token.access_token, 'new-cookie')
  assert.equal(data.fba_auth_signed_out, false)
  assert.equal(validations, 1)
})

test('非 JSON 的 401 响应也会使旧会话失效', async () => {
  const data = environment()
  await auth.saveAuthSession({ access_token: 'revoked' }, user)
  globalThis.fetch = async () => new Response('Unauthorized', { status: 401 })
  const result = await bridge.handleSiteAuth({ type: 'SITE_AUTH_GET' })
  assert.equal(result.rejectedToken, 'revoked')
  assert.equal(data.fba_auth_token, undefined)
})

test('断网退出后，旧官网页面的被动握手不能重新激活刚退出的凭据', async () => {
  const data = environment()
  await auth.saveAuthSession({ access_token: 'signed-out-token' }, user)
  globalThis.fetch = async () => { throw new Error('offline') }
  await assert.rejects(bridge.logoutExtension('signed-out-token'), /offline/)
  let calls = 0
  globalThis.fetch = async () => { calls++; return response(user) }
  const rejected = await bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken: 'signed-out-token' })
  assert.equal(rejected.rejectedToken, 'signed-out-token')
  assert.equal(data.fba_auth_token, undefined)
  assert.equal(calls, 0)
  await bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken: 'fresh-login-token' })
  assert.equal(data.fba_auth_token.access_token, 'fresh-login-token')
})

test('已登录 localhost 页面缺少桥接且遗留旧退出标记时，补注入并直接验证页面会话', async () => {
  const data = environment()
  data.fba_auth_signed_out = true
  chrome.tabs.query = async () => [
    { id: 7, url: 'http://localhost:3000/', active: true },
    { id: 8, url: 'http://localhost:8000/docs' },
  ]
  let injected = false
  chrome.tabs.sendMessage = async (id, message, options) => {
    assert.equal(id, 7)
    assert.equal(message.type, 'SITE_AUTH_READ_SESSION')
    assert.equal(options.frameId, 0)
    if (!injected) throw new Error('Receiving end does not exist')
    return { bridgeVersion: 3, origin: 'http://localhost:3000', accessToken: 'current-site-cookie' }
  }
  chrome.scripting.executeScript = async (options) => {
    assert.deepEqual(options, { target: { tabId: 7, frameIds: [0] }, files: ['site-auth.js'] })
    injected = true
  }
  const calls = []
  globalThis.fetch = async (url, options) => {
    calls.push(url)
    assert.equal(options.headers.Authorization, 'Bearer current-site-cookie')
    return response(user)
  }
  await bridge.bootstrapSiteSession()
  assert.equal(injected, true)
  assert.equal(data.fba_auth_token.access_token, 'current-site-cookie')
  assert.equal(data.fba_auth_signed_out, false)
  assert.deepEqual(calls, ['http://127.0.0.1:8000/api/v1/sys/users/me'])
})

test('无法注入或官网会话被拒绝时，不能直接删除旧退出标记', async () => {
  const data = environment()
  data.fba_auth_signed_out = true
  chrome.tabs.query = async () => [{ id: 7, url: 'http://localhost:3000/' }]
  chrome.tabs.sendMessage = async () => { throw new Error('missing bridge') }
  globalThis.fetch = async () => { throw new Error('must not restore old cookies') }
  await bridge.bootstrapSiteSession()
  assert.equal(data.fba_auth_signed_out, true)
  assert.equal(data.fba_auth_token, undefined)

  chrome.tabs.sendMessage = async () => ({ bridgeVersion: 3, origin: 'http://localhost:3000', accessToken: 'revoked-cookie' })
  globalThis.fetch = async () => response(null, 401)
  await bridge.bootstrapSiteSession()
  assert.equal(data.fba_auth_signed_out, true)
  assert.equal(data.fba_auth_token, undefined)
})

test('自动重连与官网同时握手时共用同一校验，额度流程等待登录完成', async () => {
  const data = environment()
  chrome.tabs.query = async () => [{ id: 7, url: 'http://localhost:3000/' }]
  let complete
  let calls = 0
  globalThis.fetch = async () => {
    calls++
    return new Promise((resolve) => { complete = resolve })
  }
  chrome.tabs.sendMessage = async () => {
    void bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken: 'shared-token' })
    return { bridgeVersion: 3, origin: 'http://localhost:3000', accessToken: 'shared-token' }
  }
  let finished = false
  const pending = bridge.bootstrapSiteSession().then(() => { finished = true })
  await tick()
  const sameLogin = bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken: 'shared-token' })
  assert.equal(finished, false)
  assert.equal(calls, 1)
  complete(response(user))
  await Promise.all([pending, sameLogin])
  assert.equal(data.fba_auth_token.access_token, 'shared-token')
  assert.equal(calls, 1)
})

test('读取官网 Cookie 途中主动退出，迟到的页面响应不能恢复登录', async () => {
  const data = environment()
  chrome.tabs.query = async () => [{ id: 7, url: 'http://localhost:3000/' }]
  let complete
  chrome.tabs.sendMessage = async () => new Promise((resolve) => { complete = resolve })
  globalThis.fetch = async () => { throw new Error('must not import after logout') }
  const pending = bridge.bootstrapSiteSession()
  await tick()
  await bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGOUT', expectedToken: 'old-cookie' })
  complete({ bridgeVersion: 3, origin: 'http://localhost:3000', accessToken: 'old-cookie' })
  await pending
  assert.equal(data.fba_auth_token, undefined)
})

test('旧官网或迟到的 Popup 退出消息不能中断另一个正在校验的新登录', async () => {
  const data = environment()
  await auth.saveAuthSession({ access_token: 'old-token' }, user)
  let complete
  globalThis.fetch = async () => new Promise((resolve) => { complete = resolve })
  const login = bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken: 'new-token' })
  await tick()
  await bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGOUT', expectedToken: 'old-token' })
  await bridge.logoutExtension('old-token')
  await bridge.logoutExtension('another-old-token')
  complete(response(user))
  await login
  assert.equal(data.fba_auth_token.access_token, 'new-token')
})

test('第一个官网会话被拒绝时，继续验证另一个官网的有效会话', async () => {
  const data = environment()
  chrome.tabs.query = async () => [
    { id: 1, url: 'http://localhost:3000/', active: true },
    { id: 2, url: 'http://127.0.0.1:3000/' },
  ]
  chrome.tabs.sendMessage = async (id) => ({
    bridgeVersion: 3, origin: id === 1 ? 'http://localhost:3000' : 'http://127.0.0.1:3000',
    accessToken: id === 1 ? 'revoked-token' : 'valid-token',
  })
  const checked = []
  globalThis.fetch = async (_url, options) => {
    checked.push(options.headers.Authorization)
    return options.headers.Authorization === 'Bearer revoked-token' ? response(null, 401) : response(user)
  }
  await bridge.bootstrapSiteSession()
  assert.equal(data.fba_auth_token.access_token, 'valid-token')
  assert.deepEqual(checked, ['Bearer revoked-token', 'Bearer valid-token'])
})

test('官网已撤销同一会话时重复退出成功，失效网络仍报错', async () => {
  const data = environment()
  await auth.saveAuthSession({ access_token: 'already-revoked' }, user)
  globalThis.fetch = async () => new Response('Unauthorized', { status: 401 })
  await bridge.logoutExtension('already-revoked')
  assert.equal(data.fba_auth_token, undefined)
})

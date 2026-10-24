import assert from 'node:assert/strict'
import test from 'node:test'
import { importTypeScript } from './helpers/typescript.mjs'

const auth = await importTypeScript(new URL('../src/utils/auth.ts', import.meta.url))
const bridge = await importTypeScript(new URL('../src/utils/auth-bridge.ts', import.meta.url))
const protocol = await importTypeScript(new URL('../src/utils/auth-protocol.ts', import.meta.url))
const user = { id: 7, nickname: '官网用户' }
const tick = () => new Promise(resolve => setImmediate(resolve))
const response = (data, code = 200) => new Response(JSON.stringify({ code, data }), { status: code })
function token(sid, exp = Date.now() / 1000 + 3600) {
  return `header.${Buffer.from(JSON.stringify({ session_uuid: sid, exp })).toString('base64url')}.signature`
}
function issued(sid = 'extension-session') {
  return { access_token: token(sid), refresh_token: `refresh-${sid}`, client_type: 'extension', session_uuid: sid, user }
}
function environment() {
  const data = {}
  globalThis.chrome = {
    storage: { local: {
      async get() { return { ...data } },
      async set(values) { Object.assign(data, values) },
      async remove(keys) { for (const key of keys) delete data[key] },
    } },
    tabs: { async query() { return [] } },
    scripting: { async executeScript() { throw new Error('unexpected injection') } },
  }
  return data
}

test('官网桥接仅接受准确的已登记域名与端口', () => {
  assert.ok(protocol.isTrustedSite('http://localhost:3000/profile'))
  for (const url of ['http://localhost:8000/', 'https://localhost:3000/', 'http://localhost.evil:3000/', 'invalid']) {
    assert.equal(protocol.isTrustedSite(url), false)
  }
})

test('官网登录换取独立插件会话，消息响应不暴露任何插件凭据', async () => {
  const data = environment()
  const website = token('website')
  globalThis.fetch = async (url, options) => {
    assert.match(url, /auth\/extension-session$/)
    assert.equal(options.headers.Authorization, `Bearer ${website}`)
    assert.equal(options.headers['X-Client-Type'], 'extension')
    return response(issued())
  }
  const session = await bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken: website })
  assert.notEqual(data.fba_auth_token.access_token, website)
  assert.equal(data.fba_auth_token.session_uuid, 'extension-session')
  assert.equal(data.fba_auth_site_session, 'website')
  assert.deepEqual(bridge.publicSession(session), { loggedIn: true, user, rejectedToken: undefined })
})

test('官网重复握手及自身 Token 刷新不反复签发插件会话', async () => {
  environment()
  let exchanges = 0
  globalThis.fetch = async url => {
    if (url.endsWith('/extension-session')) { exchanges++; return response(issued()) }
    return response(user)
  }
  await bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken: token('website', 2000000000) })
  await bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken: token('website', 2000000100) })
  assert.equal(exchanges, 1)
})

test('官网退出不撤销插件，插件退出只撤销自己且不会被同一官网会话自动复活', async () => {
  const data = environment()
  const website = token('website')
  const calls = []
  globalThis.fetch = async (url, options) => {
    calls.push([url, options])
    return response(url.endsWith('/extension-session') ? issued() : null)
  }
  await bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken: website })
  const extensionToken = data.fba_auth_token.access_token
  await bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGOUT', expectedToken: website })
  assert.equal(data.fba_auth_token.access_token, extensionToken)
  assert.equal(calls.length, 1)
  await bridge.logoutExtension(extensionToken)
  assert.equal(data.fba_auth_token, undefined)
  assert.equal(calls[1][1].headers.Authorization, `Bearer ${extensionToken}`)
  await bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken: website })
  assert.equal(calls.length, 2)
  assert.equal(data.fba_auth_token, undefined)
  await bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken: token('new-website') })
  assert.ok(data.fba_auth_token)
})

test('插件被踢后不会利用现有官网凭据自动抢回同端名额', async () => {
  const data = environment()
  const website = token('website')
  globalThis.fetch = async () => response(issued())
  await bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken: website })
  globalThis.fetch = async () => response(null, 401)
  await bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken: website })
  assert.equal(data.fba_auth_token, undefined)
  globalThis.fetch = async () => assert.fail('同一个来源不得重新换发')
  await bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken: website })
})

test('校验遇到网络错误保留当前会话；明确 401 才清理插件自身凭据', async () => {
  const data = environment()
  await auth.saveAuthSession(issued(), user)
  globalThis.fetch = async () => { throw new Error('offline') }
  await assert.rejects(bridge.handleSiteAuth({ type: 'SITE_AUTH_GET' }), /offline/)
  assert.ok(data.fba_auth_token)
  globalThis.fetch = async () => new Response('Unauthorized', { status: 401 })
  await bridge.handleSiteAuth({ type: 'SITE_AUTH_GET' })
  assert.equal(data.fba_auth_token, undefined)
})

test('迟到的官网换票不能覆盖新账号，并撤销未使用的新插件会话', async () => {
  const data = environment()
  let finish
  const revoked = []
  globalThis.fetch = async (url, options) => {
    if (url.endsWith('/logout')) { revoked.push(options.headers.Authorization); return response(null) }
    return new Promise(resolve => { finish = resolve })
  }
  const pending = bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken: token('website') })
  await tick()
  await auth.saveAuthSession(issued('new-account'), { id: 8 })
  finish(response(issued('late-session')))
  await pending
  assert.equal(data.fba_auth_token.session_uuid, 'new-account')
  assert.equal(revoked.length, 1)
  assert.equal(protocol.getTokenSessionId(revoked[0].slice(7)), 'late-session')
})

test('换票过程中官网退出会取消尚未建立的插件登录', async () => {
  const data = environment()
  const website = token('website')
  let finish
  globalThis.fetch = async url => url.endsWith('/logout') ? response(null) : new Promise(resolve => { finish = resolve })
  const pending = bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken: website })
  await tick()
  await bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGOUT', expectedToken: website })
  finish(response(issued()))
  await pending
  assert.equal(data.fba_auth_token, undefined)
})

test('同时握手共用一次换票请求', async () => {
  const data = environment()
  const website = token('website')
  let finish
  let calls = 0
  globalThis.fetch = async () => { calls++; return new Promise(resolve => { finish = resolve }) }
  const first = bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken: website })
  const second = bridge.handleSiteAuth({ type: 'SITE_AUTH_LOGIN', accessToken: website })
  await tick()
  finish(response(issued()))
  await Promise.all([first, second])
  assert.equal(calls, 1)
  assert.equal(data.fba_auth_token.session_uuid, 'extension-session')
})

test('补注入官网桥接后用官网 Cookie 换取独立会话', async () => {
  const data = environment()
  chrome.tabs.query = async () => [{ id: 1, url: 'http://localhost:3000/', active: true }]
  let injected = false
  chrome.tabs.sendMessage = async () => {
    if (!injected) throw new Error('missing bridge')
    return { bridgeVersion: protocol.AUTH_BRIDGE_VERSION, origin: 'http://localhost:3000', accessToken: token('website') }
  }
  chrome.scripting.executeScript = async () => { injected = true }
  globalThis.fetch = async () => response(issued())
  await bridge.bootstrapSiteSession()
  assert.ok(injected)
  assert.equal(data.fba_auth_token.session_uuid, 'extension-session')
})

test('官网关闭后通过会话接口换票，旧退出保护阻止残留 Cookie 恢复', async () => {
  const data = environment()
  let calls = 0
  globalThis.fetch = async url => {
    calls++
    return response(url.endsWith('/api/extension/session') ? { token: { access_token: token('website') } } : issued())
  }
  await bridge.bootstrapSiteSession()
  assert.equal(data.fba_auth_token.session_uuid, 'extension-session')
  await auth.clearAuthSession()
  data.fba_auth_signed_out = true
  await bridge.bootstrapSiteSession()
  assert.equal(calls, 2)
})

test('插件过期并发请求只刷新一次，续期仍属于同一插件会话', async () => {
  const data = environment()
  const expired = { ...issued(), access_token: token('extension-session', 1) }
  await auth.saveAuthSession(expired, user, 'website')
  let calls = 0
  globalThis.fetch = async (url, options) => {
    calls++
    assert.match(url, /auth\/refresh$/)
    assert.equal(JSON.parse(options.body).refresh_token, expired.refresh_token)
    assert.equal(options.headers['X-Client-Type'], 'extension')
    await tick()
    return response(issued())
  }
  await Promise.all([auth.getRequestAuthSession(), auth.getRequestAuthSession()])
  assert.equal(calls, 1)
  assert.equal(data.fba_auth_site_session, 'website')
  assert.equal(data.fba_auth_token.session_uuid, 'extension-session')
})

test('插件刷新过程中退出或切换账号，迟到结果不会恢复旧会话', async () => {
  const data = environment()
  await auth.saveAuthSession({ ...issued(), access_token: token('extension-session', 1) }, user)
  let finish
  globalThis.fetch = async () => new Promise(resolve => { finish = resolve })
  const pending = auth.getRequestAuthSession()
  await tick()
  await auth.clearAuthSession()
  finish(response(issued()))
  await pending
  assert.equal(data.fba_auth_token, undefined)
})

test('插件刷新网络错误保留凭据，明确撤销清理本地且不发起重新登录', async () => {
  const data = environment()
  await auth.saveAuthSession({ ...issued(), access_token: token('extension-session', 1) }, user)
  globalThis.fetch = async () => { throw new Error('offline') }
  await assert.rejects(auth.getRequestAuthSession(), /offline/)
  assert.ok(data.fba_auth_token)
  globalThis.fetch = async () => response(null, 401)
  await auth.getRequestAuthSession()
  assert.equal(data.fba_auth_token, undefined)
})

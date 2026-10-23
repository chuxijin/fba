import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'
import { webcrypto } from 'node:crypto'
import { compileSource, importTypeScript } from './helpers/typescript.mjs'

const source = await readFile(new URL('../../web/app/plugins/extension-auth.client.ts', import.meta.url), 'utf8')
const code = compileSource(source)
const protocol = await importTypeScript(new URL('../src/utils/auth-protocol.ts', import.meta.url))
function setup(t, initial) {
  const callbacks = []
  let credential = initial
  const token = { get value() { return credential }, set value(next) {
    const previous = credential
    credential = next
    if (previous !== next) for (const fn of callbacks) fn(next, previous)
  } }
  const messages = []
  const window = new EventTarget()
  window.postMessage = (message) => messages.push(message)
  const location = { origin: 'http://localhost:3000', pathname: '/', reload() {} }
  const document = new EventTarget()
  document.hidden = false
  Object.defineProperty(document, 'cookie', { get: () => credential ? `web_token=${encodeURIComponent(credential)}` : '', configurable: true })
  const broadcasts = []
  const context = {
    window, location: { ...location, href: `${location.origin}/` }, document, crypto: webcrypto, atob,
    exports: {}, require: () => protocol,
    defineNuxtPlugin: (fn) => fn(), useCookie: (key) => key === 'web_token' ? token : { value: null },
    watch: (_ref, callback) => callbacks.push(callback), refreshCookie() {},
    BroadcastChannel: class { constructor() { broadcasts.push(this) } postMessage() {} close() {} },
    localStorage: { setItem() {} }, setTimeout, clearTimeout, setInterval, clearInterval,
    queueMicrotask, CustomEvent,
    $fetch: async () => ({ code: 200, data: { nickname: '官网用户' } }),
  }
  vm.runInNewContext(code, context)
  t.after(() => window.dispatchEvent(new Event('pagehide')))
  function incoming(data) {
    const event = new Event('message')
    Object.assign(event, { source: window, origin: location.origin, data: {
      channel: 'fba-site-auth-v1', direction: 'extension-to-site', ...data,
    } })
    window.dispatchEvent(event)
  }
  return { token, messages, incoming, window, document, broadcasts }
}

test('官网启动时导入扩展会话，不产生循环同步', async (t) => {
  const site = setup(t)
  // Nuxt useCookie 在首次访问且没有 Cookie 时返回 undefined，而不是 null。
  assert.equal(site.token.value, undefined)
  const request = site.messages.at(-1)
  site.incoming({ id: request.id, success: true, state: { token: { access_token: 'extension-token' }, user: { nickname: '用户' } } })
  assert.equal(site.token.value, 'extension-token')
  const count = site.messages.length
  site.incoming({ id: request.id, success: true, state: { token: { access_token: 'old' } } })
  assert.equal(site.token.value, 'extension-token')
  assert.equal(site.messages.length, count)
})
test('已明确退出的官网也能接收新会话，仅清除明确被拒绝的当前凭据', (t) => {
  const site = setup(t, null)
  let request = site.messages.at(-1)
  site.incoming({ id: request.id, success: true, state: { token: { access_token: 'new-token' } } })
  assert.equal(site.token.value, 'new-token')
  site.incoming({ type: 'changed' })
  request = site.messages.at(-1)
  site.incoming({ id: request.id, success: true, state: { rejectedToken: 'new-token', token: null } })
  assert.equal(site.token.value, null)
})
test('官网登录/退出发送明确事件，旧响应不覆盖新账号', (t) => {
  const site = setup(t)
  const old = site.messages.at(-1)
  site.token.value = 'new-account'
  assert.equal(site.messages.at(-1).type, 'SITE_AUTH_LOGIN')
  site.incoming({ id: old.id, success: true, state: { token: { access_token: 'old-account' } } })
  assert.equal(site.token.value, 'new-account')
  site.token.value = null
  assert.equal(site.messages.at(-1).type, 'SITE_AUTH_LOGOUT')
  assert.equal(site.messages.at(-1).expectedToken, 'new-account')
})
test('扩展退出通知使官网清除会话', (t) => {
  const site = setup(t, 'extension-token')
  site.incoming({ type: 'changed' })
  const request = site.messages.at(-1)
  assert.equal(request.type, 'SITE_AUTH_GET')
  site.incoming({ id: request.id, success: true, state: { token: null, user: null } })
  assert.equal(site.token.value, null)
})

test('启动、available 和资料事件在同一握手进行中时不会重复发送登录请求', (t) => {
  const site = setup(t, 'site-token')
  assert.equal(site.messages.length, 1)
  site.incoming({ type: 'available' })
  site.window.dispatchEvent(new Event('user:profile-updated'))
  assert.equal(site.messages.length, 1)
})

test('其他标签页 Cookie 变更时直接同步，未等待 Nuxt 的异步 refreshCookie', (t) => {
  const site = setup(t, 'old-token')
  Object.defineProperty(site.document, 'cookie', { get: () => 'web_token=new-token', configurable: true })
  site.broadcasts[0].onmessage()
  assert.equal(site.token.value, 'new-token')
})

import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'
import { compileSource, importTypeScript } from './helpers/typescript.mjs'

const source = await readFile(new URL('../src/content/site-auth.ts', import.meta.url), 'utf8')
const protocol = await importTypeScript(new URL('../src/utils/auth-protocol.ts', import.meta.url))
const code = compileSource(source)

test('重载扩展导致旧页面上下文失效时返回失败，诊断不包含 Cookie 值', () => {
  const window = new EventTarget()
  window.top = window
  const messages = []
  window.postMessage = (data) => messages.push(data)
  let incoming
  const chrome = { runtime: {
    id: 'test-extension',
    sendMessage() { throw new Error('Extension context invalidated.') },
    onMessage: { addListener(fn) { incoming = fn } },
  } }
  vm.runInNewContext(code, {
    exports: {}, require: () => protocol,
    window, chrome, location: { origin: 'http://localhost:3000', href: 'http://localhost:3000/' },
    document: { cookie: 'web_token=private-test-token; unrelated=secret' },
  })
  const event = new Event('message')
  Object.assign(event, { source: window, origin: 'http://localhost:3000', data: {
    channel: protocol.SITE_AUTH_CHANNEL, direction: 'site-to-extension', type: 'SITE_AUTH_LOGIN', id: 'login-1', accessToken: 'private-test-token',
  } })
  window.dispatchEvent(event)
  assert.equal(messages.at(-1).success, false)
  assert.match(messages.at(-1).error, /刷新官网页面/)
  let report
  incoming({ type: 'SITE_AUTH_DIAGNOSE' }, {}, (data) => { report = data })
  assert.equal(report.hasSiteToken, true)
  assert.equal(report.siteDetected, true)
  assert.equal(report.lastSync, 'error')
  assert.equal(JSON.stringify(report).includes('private-test-token'), false)
})

test('桥接重复注入保持单个监听器，页面会话只通过扩展内部消息读取', () => {
  const window = new EventTarget()
  window.top = window
  const posted = []
  window.postMessage = (data) => posted.push(data)
  const listeners = new Set()
  const chrome = { runtime: {
    id: 'test-extension', sendMessage() {},
    onMessage: { addListener(fn) { listeners.add(fn) }, removeListener(fn) { listeners.delete(fn) } },
  } }
  const context = vm.createContext({
    exports: {}, require: () => protocol,
    window, chrome, location: { origin: 'http://localhost:3000', href: 'http://localhost:3000/' },
    document: { cookie: `web_token=${encodeURIComponent(JSON.stringify('private-cookie'))}` },
  })
  vm.runInContext(`(() => { ${code} })()`, context)
  vm.runInContext(`(() => { ${code} })()`, context)
  assert.equal(listeners.size, 1)
  let session
  for (const listener of listeners) listener({ type: 'SITE_AUTH_READ_SESSION' }, {}, (data) => { session = data })
  assert.equal(session.accessToken, 'private-cookie')
  assert.equal(session.origin, 'http://localhost:3000')
  assert.equal(session.bridgeVersion, protocol.AUTH_BRIDGE_VERSION)
  assert.equal(JSON.stringify(posted).includes('private-cookie'), false)
})

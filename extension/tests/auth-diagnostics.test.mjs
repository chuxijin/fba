import assert from 'node:assert/strict'
import test from 'node:test'
import { importTypeScript } from './helpers/typescript.mjs'

const { collectAuthDiagnostics } = await importTypeScript(new URL('../src/utils/auth-diagnostics.ts', import.meta.url))

function environment() {
  const data = { fba_auth_token: { access_token: 'private-test-token' }, fba_auth_user: { nickname: 'private-nickname' } }
  globalThis.chrome = {
    storage: { local: { async get() { return structuredClone(data) } } },
    runtime: { getManifest: () => ({ version: '1.0.0' }) },
    permissions: { async contains() { return true } },
    scripting: { async executeScript() { return [{ frameId: 0, result: true }] } },
    tabs: {
      async query() { return [{ id: 1, url: 'http://localhost:3000/' }] },
      async sendMessage() { return { bridgeVersion: 4, siteDetected: true, hasSiteToken: true, lastSync: 'success' } },
    },
  }
  globalThis.fetch = async (url) => new Response(JSON.stringify({ code: 200, data: url.endsWith('/quota')
    ? { is_logged_in: true, user: data.fba_auth_user }
    : { token: data.fba_auth_token, user: data.fba_auth_user } }))
  return data
}

test('检查真实链路状态，报告不包含凭据或个人资料且不改登录状态', async () => {
  const data = environment()
  const before = structuredClone(data)
  const report = await collectAuthDiagnostics()
  assert.match(report, /后端 http:\/\/127.0.0.1:8000：已确认登录/)
  assert.match(report, /页面桥接：已注入 v4；官网脚本：已握手/)
  assert.match(report, /最近同步：成功/)
  assert.equal(report.includes('private-'), false)
  assert.deepEqual(data, before)
})

test('区分未注入、错误端口、未登录 Cookie 和旧版退出保护', async () => {
  const data = environment()
  data.fba_auth_signed_out = true
  chrome.tabs.query = async () => [{ id: 1, url: 'http://localhost:3000/' }, { id: 2, url: 'http://localhost:3001/' }]
  chrome.tabs.sendMessage = async () => { throw new Error('Receiving end does not exist') }
  globalThis.fetch = async (url) => new Response(JSON.stringify({ code: 200, data: url.endsWith('/quota')
    ? { is_logged_in: false } : { token: null } }))
  const report = await collectAuthDiagnostics()
  assert.match(report, /旧版退出标记/)
  assert.match(report, /页面桥接：站点访问正常，桥接未连接或版本过旧/)
  assert.match(report, /http:\/\/localhost:3001 未接入/)
  assert.match(report, /未读到有效登录 Cookie/)
})

test('区分权限关闭、服务离线和服务端拒绝，不把它们报告为游客', async () => {
  environment()
  chrome.permissions.contains = async ({ origins }) => !origins[0].includes('localhost')
  globalThis.fetch = async (url) => {
    if (url.endsWith('/quota')) return new Response('Unauthorized', { status: 401 })
    throw new Error('offline')
  }
  const report = await collectAuthDiagnostics()
  assert.match(report, /凭据被拒绝（HTTP 401）/)
  assert.match(report, /站点访问权限未开启/)
  assert.match(report, /连接失败/)
  assert.equal(report.includes('：游客'), false)
})

test('清单权限已授予但网站总开关暂停扩展时，报告实际 Blocked 而不是误报脚本断连', async () => {
  const data = environment()
  chrome.tabs.sendMessage = async () => { throw new Error('Could not establish connection. Receiving end does not exist.') }
  chrome.scripting.executeScript = async (options) => {
    assert.deepEqual(options.target, { tabId: 1, frameIds: [0] })
    assert.equal(options.func(), true)
    throw new Error('Blocked')
  }
  globalThis.fetch = async (url) => {
    if (url.startsWith('http://localhost:3000')) throw new TypeError('Failed to fetch')
    return new Response(JSON.stringify({ code: 200, data: url.endsWith('/quota') ? { is_logged_in: true } : { token: null } }))
  }
  const before = structuredClone(data)
  const report = await collectAuthDiagnostics()
  assert.match(report, /浏览器已暂停此网站上的扩展（Blocked）/)
  assert.match(report, /开启“允许在此网站使用扩展”/)
  assert.match(report, /连接失败（Failed to fetch）/)
  assert.equal(report.includes('private-'), false)
  assert.deepEqual(data, before)
})

import assert from 'node:assert/strict'
import test from 'node:test'
import { importTypeScript } from './helpers/typescript.mjs'

const PROD = { __API_BASE__: 'https://api.yzxj.vip', __IS_PROD__: true }
const DEV = { __API_BASE__: 'http://127.0.0.1:8000', __IS_PROD__: false }

const prodProtocol = await importTypeScript(new URL('../src/utils/auth-protocol.ts', import.meta.url), PROD)
const devProtocol = await importTypeScript(new URL('../src/utils/auth-protocol.ts', import.meta.url), DEV)
const prodBridge = await importTypeScript(new URL('../src/utils/auth-bridge.ts', import.meta.url), PROD)

function storage() {
  const data = {}
  return {
    data,
    local: {
      async get(keys) {
        if (!keys) return { ...data }
        const list = Array.isArray(keys) ? keys : Object.keys(keys)
        return Object.fromEntries(list.filter(key => key in data).map(key => [key, data[key]]))
      },
      async set(values) { Object.assign(data, values) },
      async remove(keys) { for (const key of keys) delete data[key] },
    },
  }
}

test('生产构建注入 HTTPS 后端，且不登记任何本地官网来源', () => {
  assert.equal(prodProtocol.BACKEND_BASE, 'https://api.yzxj.vip')
  assert.equal(prodProtocol.IS_PRODUCTION, true)
  assert.deepEqual(prodProtocol.SITE_URL_PATTERNS, [])
  for (const url of [
    'http://localhost:3000/',
    'http://127.0.0.1:3000/',
    'http://localhost:3000/profile?from=website',
    'https://api.yzxj.vip/ti/exam/1',
  ]) assert.equal(prodProtocol.isTrustedSite(url), false, url)
})

test('开发构建仍允许已登记的本地官网端口', () => {
  assert.equal(devProtocol.BACKEND_BASE, 'http://127.0.0.1:8000')
  assert.equal(devProtocol.IS_PRODUCTION, false)
  assert.deepEqual(devProtocol.SITE_URL_PATTERNS, ['http://localhost/*', 'http://127.0.0.1/*'])
  assert.equal(devProtocol.isTrustedSite('http://localhost:3000/profile'), true)
  assert.equal(devProtocol.isTrustedSite('http://127.0.0.1:3000/'), true)
})

test('生产模式启动不查询标签页、不补注入、不请求本地官网会话', async () => {
  const store = storage()
  let touched = 0
  globalThis.chrome = {
    storage: { local: store.local },
    tabs: {
      async query() { touched++; return [] },
      async sendMessage() { touched++ },
    },
    scripting: { async executeScript() { touched++ } },
  }
  globalThis.fetch = async () => { touched++; throw new Error('生产模式不应访问本地官网') }

  await prodBridge.bootstrapSiteSession()
  await prodBridge.bootstrapSiteSession()

  assert.equal(touched, 0)
  assert.deepEqual(store.data, {})
})

test('生产模式不把本地页面消息当作官网登录同步', async () => {
  const store = storage()
  let fetched = 0
  globalThis.chrome = {
    storage: { local: store.local },
    tabs: { async query() { return [] } },
  }
  globalThis.fetch = async () => { fetched++; throw new Error('unexpected') }

  assert.equal(prodProtocol.isSiteAuthMessage({ type: 'SITE_AUTH_LOGIN', accessToken: 'website-token' }), true)
  assert.equal(prodProtocol.isTrustedSite('http://localhost:3000/'), false)
  assert.equal(fetched, 0)
  assert.deepEqual(store.data, {})
})

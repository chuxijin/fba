import assert from 'node:assert/strict'
import test from 'node:test'
import { importTypeScript } from './helpers/typescript.mjs'

const auth = await importTypeScript(new URL('../src/utils/auth.ts', import.meta.url))
const { createAccountStore } = await importTypeScript(new URL('../src/utils/account-state.ts', import.meta.url))

function environment(token, user = { nickname: '旧用户' }) {
  const data = token ? { fba_auth_token: token, fba_auth_user: user } : {}
  const listeners = new Set()
  const messages = []
  function emit(changes) {
    for (const listener of [...listeners]) listener(changes, 'local')
  }
  globalThis.chrome = {
    storage: {
      local: {
        async get() { return { ...data } },
        async set(values) {
          Object.assign(data, values)
          queueMicrotask(() => emit(Object.fromEntries(Object.entries(values).map(([key, newValue]) => [key, { newValue }]))))
        },
        async remove(keys) {
          keys.forEach((key) => delete data[key])
          queueMicrotask(() => emit(Object.fromEntries(keys.map((key) => [key, {}]))))
        },
      },
      onChanged: { addListener: (fn) => listeners.add(fn), removeListener: (fn) => listeners.delete(fn) },
    },
    runtime: { sendMessage: (_message, callback) => messages.push(callback) },
    tabs: { async query() { return [] }, async sendMessage() {} },
  }
  return { data, listeners, messages, emit }
}
function jwt(exp) {
  return { access_token: `header.${Buffer.from(JSON.stringify({ exp })).toString('base64url')}.signature` }
}
function quota(is_logged_in, remaining_quota = 3) {
  return { is_logged_in, remaining_quota, daily_limit: 5, used_count: 5 - remaining_quota }
}
function response(data, code = 200, status = 200) {
  return new Response(JSON.stringify({ code, data }), { status })
}
const tick = () => new Promise((resolve) => setImmediate(resolve))

test('首次打开保持确认中；并发刷新共用请求，完成后显示真实用户', async () => {
  const env = environment(jwt(Date.now() / 1000 + 600))
  const store = createAccountStore()
  const states = []
  const stop = store.subscribe((state) => states.push(state))
  const first = store.refresh()
  assert.equal(store.refresh(), first)
  assert.equal(env.messages.length, 1)
  assert.ok(states.every((state) => state.status === 'loading'))
  env.messages[0]({ success: true, data: { ...quota(true), user: { nickname: '真实用户' } } })
  await first
  assert.equal(states.at(-1).quota.user.nickname, '真实用户')
  stop()
  assert.equal(env.listeners.size, 0)
})

test('请求期间退出登录：旧用户响应不会覆盖游客状态', async () => {
  const env = environment(jwt(Date.now() / 1000 + 600))
  const store = createAccountStore()
  const states = []
  const stop = store.subscribe((state) => states.push(state))
  const old = store.refresh()
  await auth.clearAuthSession()
  await tick()
  assert.equal(env.messages.length, 2)
  env.messages[1]({ success: true, data: quota(false) })
  await tick()
  env.messages[0]({ success: true, data: quota(true) })
  await old
  assert.equal(states.at(-1).quota.is_logged_in, false)
  assert.ok(!states.some((state) => state.status === 'ready' && state.quota.is_logged_in))
  stop()
})

test('网络失败显示错误且不伪造额度；允许重试', async () => {
  const env = environment(null)
  const store = createAccountStore()
  const states = []
  const stop = store.subscribe((state) => states.push(state))
  const failed = store.refresh()
  env.messages[0]({ success: false, error: '网络不可用' })
  await failed
  assert.deepEqual(states.at(-1), { status: 'error', message: '网络不可用' })
  const retry = store.refresh()
  env.messages[1]({ success: true, data: quota(false, 0) })
  await retry
  assert.equal(states.at(-1).quota.remaining_quota, 0)
  stop()
})

test('打开视图响应登录和导出额度变更；后台错误不重复直连', async () => {
  const env = environment(null)
  const store = createAccountStore()
  const states = []
  const stop = store.subscribe((state) => states.push(state))
  let task = store.refresh()
  env.messages[0]({ success: true, data: quota(false) })
  await task
  await auth.saveAuthSession(jwt(Date.now() / 1000 + 600), { nickname: '新用户' })
  await tick()
  env.messages[1]({ success: true, data: { ...quota(true), user: { nickname: '新用户' } } })
  await tick()
  assert.equal(states.at(-1).quota.user.nickname, '新用户')
  env.emit({ fba_quota_revision: { newValue: 'exported' } })
  env.messages[2]({ success: true, data: quota(true, 2) })
  await tick()
  assert.equal(states.at(-1).quota.remaining_quota, 2)
  let directFetches = 0
  globalThis.fetch = async () => { directFetches++; throw new Error('不应直连') }
  task = auth.fetchCurrentQuota()
  env.messages[3]({ success: false, error: '服务异常' })
  await assert.rejects(task, /服务异常/)
  assert.equal(directFetches, 0)
  stop()
})

test('即使存有 token，后端返回未登录仍以服务端为准并清理旧凭据', async () => {
  const env = environment(jwt(Date.now() / 1000 + 600))
  globalThis.fetch = async () => response(quota(false))
  const result = await auth.requestCurrentQuota()
  assert.equal(result.is_logged_in, false)
  assert.equal(result.user, undefined)
  assert.equal(env.data.fba_auth_token, undefined)
})

test('过期 token 不发送；JWT exp 优先于无时区存储日期', async () => {
  const token = { ...jwt(Date.now() / 1000 - 60), access_token_expire_time: '2099-01-01T00:00:00' }
  const env = environment(token)
  const headers = []
  globalThis.fetch = async (_url, options) => { headers.push(options.headers); return response(quota(false)) }
  assert.equal(auth.isTokenExpired(token), true)
  assert.equal((await auth.requestCurrentQuota()).is_logged_in, false)
  assert.equal(headers.length, 1)
  assert.equal(headers[0].Authorization, undefined)
  assert.equal(env.data.fba_auth_token, undefined)
})

test('401（包括非 JSON 响应）清理凭据后只重试游客 quota', async () => {
  for (const unauthorized of [new Response('Unauthorized', { status: 401 }), response(null, 401)]) {
    const env = environment(jwt(Date.now() / 1000 + 600))
    let calls = 0
    globalThis.fetch = async () => ++calls === 1 ? unauthorized : response(quota(false))
    assert.equal((await auth.requestCurrentQuota()).is_logged_in, false)
    assert.equal(calls, 2)
    assert.equal(env.data.fba_auth_token, undefined)
  }
})

test('后台慢请求遇到新登录：重读新凭据，旧 401 不清除新账号', async () => {
  const env = environment({ access_token: 'old-token' })
  let finishOld
  const headers = []
  globalThis.fetch = async (_url, options) => {
    headers.push(options.headers.Authorization)
    if (headers.length === 1) return new Promise((resolve) => { finishOld = resolve })
    return response(quota(true))
  }
  const pending = auth.requestCurrentQuota()
  await tick()
  await auth.saveAuthSession({ access_token: 'new-token' }, { nickname: '新用户' })
  finishOld(new Response('Unauthorized', { status: 401 }))
  const result = await pending
  assert.equal(result.user.nickname, '新用户')
  assert.equal(env.data.fba_auth_token.access_token, 'new-token')
  assert.deepEqual(headers, ['Bearer old-token', 'Bearer new-token'])
})

test('异常响应与网络中断不会清除凭据，也不返回伪造的 5 次', async () => {
  const env = environment({ access_token: 'valid-token' })
  globalThis.fetch = async () => response({ ...quota(true), remaining_quota: undefined })
  await assert.rejects(auth.requestCurrentQuota(), /无效额度/)
  globalThis.fetch = async () => { throw new Error('offline') }
  await assert.rejects(auth.requestCurrentQuota(), /offline/)
  assert.equal(env.data.fba_auth_token.access_token, 'valid-token')
})

test('后台合并来自不同视图的并发额度请求', async () => {
  environment({ access_token: 'valid-token' })
  let handleMessage
  chrome.runtime.onInstalled = { addListener() {} }
  chrome.tabs = { async query() { return [] } }
  chrome.runtime.onMessage = { addListener(fn) { handleMessage = fn } }
  await importTypeScript(new URL('../src/background/index.ts', import.meta.url))
  let finish
  let calls = 0
  globalThis.fetch = async () => {
    calls++
    return new Promise((resolve) => { finish = resolve })
  }
  const results = []
  assert.equal(handleMessage({ type: 'GET_QUOTA' }, {}, (result) => results.push(result)), true)
  handleMessage({ type: 'GET_QUOTA' }, {}, (result) => results.push(result))
  await tick()
  assert.equal(calls, 1)
  finish(response(quota(false)))
  await tick()
  assert.equal(results.length, 2)
  assert.ok(results.every((result) => result.success && !result.data.is_logged_in))
})

test('账户视图持续打开时，到期自动重新确认', async () => {
  const env = environment(jwt((Date.now() + 100) / 1000))
  const store = createAccountStore()
  const states = []
  const stop = store.subscribe((state) => states.push(state))
  const first = store.refresh()
  env.messages[0]({ success: true, data: quota(true) })
  await first
  await new Promise((resolve) => setTimeout(resolve, 150))
  assert.equal(env.messages.length, 2)
  assert.equal(states.at(-1).status, 'loading')
  env.messages[1]({ success: true, data: quota(false) })
  await tick()
  assert.equal(states.at(-1).quota.is_logged_in, false)
  stop()
})

async function confirmAccount(env, loggedIn = true, base = 'http://127.0.0.1:8000') {
  globalThis.fetch = async () => response(quota(loggedIn))
  await auth.requestCurrentQuota(base)
  assert.ok(env.data.fba_account_cache)
}

function waitForState(store, predicate) {
  return new Promise((resolve, reject) => {
    let stop = () => {}
    const timer = setTimeout(() => { stop(); reject(new Error('状态未在一秒内就绪')) }, 1000)
    stop = store.subscribe((state) => {
      if (predicate(state)) queueMicrotask(() => { stop(); clearTimeout(timer); resolve(state) })
    })
  })
}

test('重新打开文档时先显示已确认缓存，不等待后台响应，再更新真实额度', async (t) => {
  const env = environment(jwt(Date.now() / 1000 + 600), { nickname: '缓存用户', avatar: 'avatar.png' })
  await confirmAccount(env)
  for (let opening = 0; opening < 2; opening++) {
    const store = createAccountStore()
    const states = []
    const stop = store.subscribe((state) => states.push(state))
    t.after(stop)
    const cached = waitForState(store, (state) => state.status === 'ready')
    const pending = store.refresh()
    await cached
    assert.equal(states.at(-1).status, 'ready')
    assert.equal(states.at(-1).refreshing, true)
    assert.equal(states.at(-1).quota.user.nickname, '缓存用户')
    assert.equal(states.at(-1).quota.user.avatar, 'avatar.png')
    env.messages[opening]({ success: true, data: { ...quota(true, 1), user: { nickname: '缓存用户' } } })
    await pending
    assert.equal(states.at(-1).refreshing, undefined)
    assert.equal(states.at(-1).quota.remaining_quota, 1)
    stop()
  }
})

test('缓存账号遇到断网保持昵称；重试期间不隐藏账号，成功后恢复真实额度', async (t) => {
  const env = environment(jwt(Date.now() / 1000 + 600))
  await confirmAccount(env)
  const store = createAccountStore()
  const states = []
  const stop = store.subscribe((state) => states.push(state))
  t.after(stop)
  let pending = store.refresh()
  // 网络失败可能比本地读取更快，仍应等本地快照完成后显示缓存身份。
  env.messages[0]({ success: false, error: 'offline' })
  await pending
  assert.equal(states.at(-1).status, 'ready')
  assert.equal(states.at(-1).quota.user.nickname, '旧用户')
  assert.equal(states.at(-1).refreshError, 'offline')
  pending = store.refresh()
  assert.equal(states.at(-1).status, 'ready')
  assert.equal(states.at(-1).refreshing, true)
  env.messages[1]({ success: true, data: quota(true, 2) })
  await pending
  assert.equal(states.at(-1).quota.remaining_quota, 2)
  assert.equal(states.at(-1).refreshError, undefined)
  stop()
})

test('缓存绑定凭据和服务端，拒绝过期、超时、无有效期以及损坏缓存', async () => {
  const original = jwt(Date.now() / 1000 + 600)
  const env = environment(original)
  await confirmAccount(env)
  const cache = structuredClone(env.data.fba_account_cache)
  assert.match(cache.sessionKey, /^[0-9a-f]{64}$/)
  assert.ok(!JSON.stringify(cache).includes(original.access_token))
  assert.equal((await auth.readCachedAccount('http://127.0.0.1:8000/')).quota.user.nickname, '旧用户')
  assert.equal(await auth.readCachedAccount('https://different.example'), null)
  for (const token of [null, jwt(Date.now() / 1000 - 1), jwt(Date.now() / 1000 + 800), { access_token: 'no-expiry' }]) {
    env.data.fba_auth_token = token
    assert.equal(await auth.readCachedAccount('http://127.0.0.1:8000'), null)
  }
  env.data.fba_auth_token = original
  for (const changed of [
    { confirmedAt: Date.now() - 86400001 },
    { confirmedAt: Date.now() + 60000 },
    { quota: { ...quota(true), remaining_quota: '3' } },
    { version: 999 },
  ]) {
    env.data.fba_account_cache = { ...cache, ...changed }
    assert.equal(await auth.readCachedAccount('http://127.0.0.1:8000'), null)
  }
})

test('缓存遇到退出/新登录立即失效，迟到的旧身份不能覆盖', async (t) => {
  const env = environment(jwt(Date.now() / 1000 + 600))
  await confirmAccount(env)
  const store = createAccountStore()
  const states = []
  const stop = store.subscribe((state) => states.push(state))
  t.after(stop)
  const cached = waitForState(store, (state) => state.status === 'ready')
  const old = store.refresh()
  await cached
  assert.equal(states.at(-1).quota.user.nickname, '旧用户')
  await auth.saveAuthSession(jwt(Date.now() / 1000 + 900), { nickname: '新账号' })
  await tick()
  assert.equal(states.at(-1).status, 'loading')
  assert.equal(env.data.fba_account_cache, null)
  env.messages[1]({ success: true, data: { ...quota(true), user: { nickname: '新账号' } } })
  await tick()
  env.messages[0]({ success: true, data: { ...quota(true), user: { nickname: '旧用户' } } })
  await old
  assert.equal(states.at(-1).quota.user.nickname, '新账号')
  await auth.clearAuthSession()
  await tick()
  assert.equal(states.at(-1).status, 'loading')
  assert.equal(env.data.fba_account_cache, undefined)
  env.messages[2]({ success: true, data: quota(false) })
  await tick()
  assert.equal(states.at(-1).quota.is_logged_in, false)
  stop()
})

test('有缓存时额度扣减更新不隐藏账号；缓存写入不触发重复请求', async (t) => {
  const env = environment(jwt(Date.now() / 1000 + 600))
  await confirmAccount(env)
  const store = createAccountStore()
  const states = []
  const stop = store.subscribe((state) => states.push(state))
  t.after(stop)
  const first = store.refresh()
  await tick()
  env.messages[0]({ success: true, data: { ...quota(true), user: { nickname: '旧用户' } } })
  await first
  await confirmAccount(env)
  await tick()
  assert.equal(env.messages.length, 1)
  env.emit({ fba_quota_revision: { newValue: 'new-export' } })
  assert.equal(states.at(-1).status, 'ready')
  assert.equal(states.at(-1).refreshing, true)
  env.messages[1]({ success: true, data: quota(true, 0) })
  await tick()
  assert.equal(states.at(-1).quota.remaining_quota, 0)
  stop()
})

test('游客缓存只在未持有凭据且五分钟内使用；后台拒绝登录后缓存游客', async () => {
  const env = environment(null)
  await confirmAccount(env, false)
  assert.equal((await auth.readCachedAccount('http://127.0.0.1:8000')).quota.is_logged_in, false)
  env.data.fba_account_cache.confirmedAt = Date.now() - 300001
  assert.equal(await auth.readCachedAccount('http://127.0.0.1:8000'), null)
  env.data.fba_account_cache.confirmedAt = Date.now()
  env.data.fba_auth_token = jwt(Date.now() / 1000 + 600)
  assert.equal(await auth.readCachedAccount('http://127.0.0.1:8000'), null)
  await confirmAccount(env, false)
  assert.equal(env.data.fba_auth_token, undefined)
  assert.equal(env.data.fba_account_cache.sessionKey, 'guest')
})

test('导出发生在查询途中，后台不会缓存扣减前的额度', async () => {
  const env = environment(jwt(Date.now() / 1000 + 600))
  let finish
  let calls = 0
  globalThis.fetch = async () => ++calls === 1
    ? new Promise((resolve) => { finish = resolve }) : response(quota(true, 1))
  const pending = auth.requestCurrentQuota()
  await tick()
  await chrome.storage.local.set({ fba_quota_revision: 'export-completed' })
  finish(response(quota(true, 3)))
  assert.equal((await pending).remaining_quota, 1)
  assert.equal(env.data.fba_account_cache.quota.remaining_quota, 1)
  assert.equal(calls, 2)
})

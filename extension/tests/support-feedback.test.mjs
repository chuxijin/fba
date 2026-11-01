import assert from 'node:assert/strict'
import test from 'node:test'
import { importTypeScript } from './helpers/typescript.mjs'

const auth = await importTypeScript(new URL('../src/utils/auth.ts', import.meta.url))
const support = await importTypeScript(new URL('../src/utils/support.ts', import.meta.url))

const BASE = 'https://api.yzxj.vip'
const JSON_HEADERS = { 'content-type': 'application/json' }
const tick = () => new Promise(resolve => setImmediate(resolve))

function token(exp = Date.now() / 1000 + 3600) {
  return `header.${Buffer.from(JSON.stringify({ session_uuid: 'extension', exp })).toString('base64url')}.signature`
}

function environment({ accessToken } = {}) {
  const data = accessToken ? { fba_auth_token: { access_token: accessToken }, fba_auth_user: { nickname: '学员' } } : {}
  globalThis.chrome = {
    storage: { local: {
      async get(keys) {
        if (!keys) return { ...data }
        const list = Array.isArray(keys) ? keys : Object.keys(keys)
        return Object.fromEntries(list.filter(key => key in data).map(key => [key, data[key]]))
      },
      async set(values) { Object.assign(data, values) },
      async remove(keys) { for (const key of keys) delete data[key] },
    } },
    runtime: { getManifest: () => ({ version: '1.0.3' }) },
  }
  return data
}

function capture(response, { base = BASE } = {}) {
  const requests = []
  globalThis.fetch = async (url, options = {}) => {
    requests.push({ url: String(url).replace(base, ''), options })
    return response()
  }
  return requests
}

const ok = (data = null) => () => new Response(JSON.stringify({ code: 200, data }), { status: 200, headers: JSON_HEADERS })

test('匿名反馈只提交类型、内容与选填联系方式，并标记为匿名', async () => {
  environment()
  const requests = capture(ok())
  const result = await support.submitExtensionFeedback({
    feedbackType: 'bug', content: '  排版后页脚错位  ', contact: '',
    pageUrl: 'https://spa.fenbi.com/ti/exam/1?token=secret',
    paper: { title: '内部试卷' }, referrer: 'https://evil.test',
  })
  assert.deepEqual(result, { anonymous: true, accountChanged: false })
  assert.equal(requests.length, 1)
  assert.ok(requests[0].url.endsWith('/api/v1/feedbacks'))
  assert.equal(requests[0].options.method, 'POST')
  assert.equal(requests[0].options.headers.Authorization, undefined)
  assert.equal(requests[0].options.headers['X-Client-Type'], 'extension')
  const body = JSON.parse(requests[0].options.body)
  assert.deepEqual(Object.keys(body).sort(), [
    'content', 'feedback_type', 'source_app', 'source_platform', 'target_id', 'target_type',
  ])
  assert.deepEqual(body, {
    feedback_type: 'bug',
    content: '排版后页脚错位',
    source_app: 'gongkao_extension',
    source_platform: 'chrome-extension',
    target_type: 'extension',
    target_id: '1.0.3',
  })
  assert.equal(JSON.stringify(body).includes('fenbi'), false)
  assert.equal(JSON.stringify(body).includes('evil'), false)
})

test('登录提交附带 Bearer 凭据与选填联系方式，并返回非匿名', async () => {
  const accessToken = token()
  environment({ accessToken })
  const requests = capture(ok())
  assert.deepEqual(await support.submitExtensionFeedback({
    feedbackType: 'experience', content: '好用', contact: 'reader@example.com',
  }), { anonymous: false, accountChanged: false })
  assert.equal(requests[0].options.headers.Authorization, `Bearer ${accessToken}`)
  const body = JSON.parse(requests[0].options.body)
  assert.equal(body.contact, 'reader@example.com')
  assert.equal(body.feedback_type, 'experience')
})

test('反馈内容、类型与联系方式在发请求前校验', async () => {
  environment()
  const requests = capture(ok())
  const invalid = [
    [{ feedbackType: 'bug', content: '' }, /1至500字/],
    [{ feedbackType: 'bug', content: '   ' }, /1至500字/],
    [{ feedbackType: 'bug', content: 'x'.repeat(501) }, /1至500字/],
    [{ feedbackType: 'unknown', content: '内容' }, /有效的反馈类型/],
    [{ content: '内容' }, /有效的反馈类型/],
    [{ feedbackType: 'bug', content: '内容', contact: 'x'.repeat(101) }, /最多100字/],
    [{ feedbackType: 'bug', content: '内容', contact: 42 }, /最多100字/],
  ]
  for (const [input, message] of invalid) {
    await assert.rejects(support.submitExtensionFeedback(input), message)
  }
  assert.equal(requests.length, 0)
})

test('过期凭据提交前报错，不静默转匿名也不提交', async () => {
  const data = environment({ accessToken: token(Date.now() / 1000 - 60) })
  const requests = capture(ok())
  await assert.rejects(
    support.submitExtensionFeedback({ feedbackType: 'bug', content: '内容' }),
    /登录已失效，请重新登录后提交，或明确退出登录后匿名反馈/,
  )
  assert.equal(requests.length, 0)
  assert.equal(data.fba_auth_token, undefined)
})

test('提交成功后本地读取失败仍返回成功，并标记账户已变化', async () => {
  environment({ accessToken: token() })
  const store = globalThis.chrome.storage.local
  const originalGet = store.get
  let reads = 0
  store.get = async (keys) => {
    reads++
    if (reads === 3) throw new Error('本地存储暂时不可用')
    return originalGet(keys)
  }
  const requests = capture(ok())
  assert.deepEqual(
    await support.submitExtensionFeedback({ feedbackType: 'bug', content: '内容' }),
    { anonymous: false, accountChanged: true },
  )
  assert.equal(requests.length, 1)
  assert.equal(requests[0].options.method, 'POST')
})

test('提交期间切换账号会标记账户已变化，结果不能算到新账号', async () => {
  environment({ accessToken: token() })
  let finish
  globalThis.fetch = async () => new Promise(resolve => { finish = resolve })
  const pending = support.submitExtensionFeedback({ feedbackType: 'bug', content: '内容' })
  await tick()
  await auth.saveAuthSession({ access_token: token(Date.now() / 1000 + 7200) }, { nickname: '新账号' })
  finish(new Response(JSON.stringify({ code: 200, data: null }), { status: 200, headers: JSON_HEADERS }))
  assert.deepEqual(await pending, { anonymous: false, accountChanged: true })
})

test('我的反馈要求登录，并校验页码与响应结构', async () => {
  environment()
  let requests = capture(ok({ items: [], total: 0 }))
  for (const page of [0, -1, 1.5, '1', 10001, undefined, null]) {
    await assert.rejects(support.listExtensionFeedback(page), /反馈记录页码无效/, String(page))
  }
  assert.equal(requests.length, 0)
  await assert.rejects(support.listExtensionFeedback(1), /请先在插件弹窗登录/)
  assert.equal(requests.length, 0)

  environment({ accessToken: token(Date.now() / 1000 - 60) })
  requests = capture(ok({ items: [], total: 0 }))
  await assert.rejects(
    support.listExtensionFeedback(1),
    /请先在插件弹窗登录/,
  )
  assert.equal(requests.length, 0)
})

test('登录后按页读取反馈，返回服务端记录与总数', async () => {
  const accessToken = token()
  environment({ accessToken })
  const payload = { items: [{ status: 'resolved', content: '已处理', reply_content: '感谢反馈' }], total: 25 }
  const requests = capture(ok(payload))
  assert.deepEqual(await support.listExtensionFeedback(2), payload)
  assert.ok(requests[0].url.endsWith('/api/v1/feedbacks/mine?page=2&size=10'))
  assert.equal(requests[0].options.headers.Authorization, `Bearer ${accessToken}`)
})

test('登录过期与异常响应不展示越权或伪造记录', async () => {
  environment({ accessToken: token(Date.now() / 1000 - 60) })
  let requests = capture(ok({ items: [], total: 0 }))
  await assert.rejects(support.listExtensionFeedback(1), /请先在插件弹窗登录/)
  assert.equal(requests.length, 0)

  environment({ accessToken: token() })
  requests = capture(ok({ items: 'nope', total: 0 }))
  await assert.rejects(support.listExtensionFeedback(1), /反馈记录响应异常/)
  requests = capture(ok(null))
  await assert.rejects(support.listExtensionFeedback(1), /反馈记录响应异常/)
})

test('迟到的反馈列表不能在新账号下展示', async () => {
  environment({ accessToken: token() })
  let finish
  globalThis.fetch = async () => new Promise(resolve => { finish = resolve })
  const pending = support.listExtensionFeedback(1)
  await tick()
  await auth.saveAuthSession({ access_token: token(Date.now() / 1000 + 7200) }, { nickname: '新账号' })
  finish(new Response(JSON.stringify({
    code: 200, data: { items: [{ content: '旧账号记录' }], total: 1 },
  }), { status: 200, headers: JSON_HEADERS }))
  await assert.rejects(pending, /账号已变化，请重新加载记录/)
})

test('反馈请求后端异常时原样抛出可展示信息', async () => {
  environment()
  globalThis.fetch = async () => new Response(JSON.stringify({ code: 422, msg: '反馈内容不合规' }), {
    status: 422, headers: JSON_HEADERS,
  })
  await assert.rejects(
    support.submitExtensionFeedback({ feedbackType: 'bug', content: '内容' }),
    /反馈内容不合规/,
  )
  const accessToken = token()
  environment({ accessToken })
  globalThis.fetch = async () => { throw new Error('offline') }
  await assert.rejects(support.listExtensionFeedback(1), /offline/)
})

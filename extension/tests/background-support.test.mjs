import assert from 'node:assert/strict'
import test from 'node:test'
import { importTypeScript } from './helpers/typescript.mjs'

const data = {}
const messageListeners = []
const storageListeners = []
const created = []

function token(exp = Date.now() / 1000 + 3600) {
  return `header.${Buffer.from(JSON.stringify({ session_uuid: 'extension', exp })).toString('base64url')}.signature`
}

globalThis.chrome = {
  runtime: {
    onMessage: { addListener(fn) { messageListeners.push(fn) } },
    getURL: path => `chrome-extension://test/${path}`,
    getManifest: () => ({ version: '1.0.3' }),
    lastError: undefined,
  },
  storage: {
    local: {
      async get(keys) {
        if (!keys) return { ...data }
        const list = Array.isArray(keys) ? keys : Object.keys(keys)
        return Object.fromEntries(list.filter(key => key in data).map(key => [key, data[key]]))
      },
      async set(values) { Object.assign(data, values) },
      async remove(keys) { for (const key of keys) delete data[key] },
    },
    onChanged: { addListener(fn) { storageListeners.push(fn) } },
  },
  tabs: {
    async query() { return [] },
    async sendMessage() {},
    async create(options) { created.push(options) },
  },
}

await importTypeScript(new URL('../src/background/index.ts', import.meta.url))
const onMessage = messageListeners[0]

const SUPPORT = 'chrome-extension://test/support.html'
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

function reset() {
  for (const key of Object.keys(data)) delete data[key]
  created.length = 0
}

function send(message, sender = { url: `${SUPPORT}#feedback`, frameId: 0 }) {
  return new Promise(resolve => { onMessage(message, sender, resolve) })
}

test('意见反馈入口固定打开插件内 support.html#feedback，忽略调用方传入的地址', async () => {
  reset()
  for (const payload of [{ section: 'help' }, { url: 'https://evil.test/' }, undefined]) {
    created.length = 0
    const returned = await send({ type: 'OPEN_SUPPORT', payload }, { url: 'chrome-extension://test/content.js', frameId: 0 })
    assert.deepEqual(returned, { success: true })
    assert.deepEqual(created, [{ url: `${SUPPORT}#feedback` }])
  }
})

test('仅插件内 support.html 可以提交反馈与读取历史', async () => {
  reset()
  let requests = 0
  globalThis.fetch = async () => { requests++; return json({ code: 200, data: { anonymous: true } }) }

  for (const senderUrl of [
    'chrome-extension://test/content.js',
    'chrome-extension://test/support.html.evil',
    'chrome-extension://test/other/support.html',
    undefined,
  ]) {
    const returned = await send(
      { type: 'SUBMIT_FEEDBACK', payload: { feedbackType: 'bug', content: '内容' } },
      { url: senderUrl, frameId: 0 },
    )
    assert.deepEqual(returned, { success: false, error: '请从插件意见反馈页面操作' })
    assert.equal(onMessage(
      { type: 'LIST_FEEDBACK', payload: { page: 1 } }, { url: senderUrl, frameId: 0 }, () => {},
    ), false)
  }
  assert.equal(requests, 0)

  // 带查询串或锚点的插件页仍视为同一页面。
  for (const senderUrl of [`${SUPPORT}#feedback`, `${SUPPORT}?from=popup`, SUPPORT]) {
    const returned = await send(
      { type: 'SUBMIT_FEEDBACK', payload: { feedbackType: 'bug', content: '内容' } },
      { url: senderUrl, frameId: 0 },
    )
    assert.deepEqual(returned, { success: true, data: { anonymous: true, accountChanged: false } })
  }
  assert.equal(requests, 3)
})

test('后台把反馈提交与分页读取转交支持服务，并回传匿名标记', async () => {
  reset()
  const requests = []
  globalThis.fetch = async (url, options = {}) => {
    requests.push({ url, options })
    if (String(url).includes('/feedbacks/mine')) return json({ code: 200, data: { items: [{ content: '记录' }], total: 1 } })
    return json({ code: 200, data: null })
  }

  const submitted = await send({
    type: 'SUBMIT_FEEDBACK',
    payload: { feedbackType: 'content_error', content: '选项排版错误', contact: '' },
  })
  assert.deepEqual(submitted, { success: true, data: { anonymous: true, accountChanged: false } })
  const body = JSON.parse(requests[0].options.body)
  assert.equal(body.feedback_type, 'content_error')
  assert.equal(body.content, '选项排版错误')
  assert.equal(body.target_id, '1.0.3')
  assert.equal(requests[0].options.headers.Authorization, undefined)

  data.fba_auth_token = { access_token: token() }
  data.fba_auth_user = { nickname: '学员' }
  const listed = await send({ type: 'LIST_FEEDBACK', payload: { page: 3 } })
  assert.deepEqual(listed, { success: true, data: { items: [{ content: '记录' }], total: 1 } })
  assert.match(requests[1].url, /\/api\/v1\/feedbacks\/mine\?page=3&size=10$/)
  assert.equal(requests[1].options.headers.Authorization, `Bearer ${data.fba_auth_token.access_token}`)
})

test('反馈校验失败与后端异常都如实回传，不伪造成功', async () => {
  reset()
  let requests = 0
  globalThis.fetch = async () => { requests++; return json({ code: 500, msg: '服务不可用' }, 500) }

  assert.deepEqual(
    await send({ type: 'SUBMIT_FEEDBACK', payload: { feedbackType: 'bug', content: '   ' } }),
    { success: false, error: '请填写1至500字的反馈内容' },
  )
  assert.equal(requests, 0)

  const failed = await send({
    type: 'SUBMIT_FEEDBACK', payload: { feedbackType: 'bug', content: '内容' },
  })
  assert.deepEqual(failed, { success: false, error: '服务不可用' })

  const anonymousList = await send({ type: 'LIST_FEEDBACK', payload: { page: 1 } })
  assert.deepEqual(anonymousList, { success: false, error: '请先在插件弹窗登录，再查看反馈记录' })
})

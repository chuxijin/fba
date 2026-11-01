import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'
import { compileSource } from './helpers/typescript.mjs'

const source = await readFile(new URL('../src/support/support.ts', import.meta.url), 'utf8')
const code = compileSource(source)

function createElement(tag = 'div') {
  const listeners = {}
  const element = {
    tagName: tag.toUpperCase(),
    children: [],
    textContent: '',
    className: '',
    value: '',
    disabled: false,
    focused: false,
    style: {},
    dataset: {},
    attributes: {},
    innerHTMLWrites: 0,
    addEventListener(type, fn) { (listeners[type] ||= []).push(fn) },
    dispatch(type, event = {}) {
      const target = { preventDefault() {}, target: element, ...event }
      return Promise.all((listeners[type] || []).map(fn => fn.call(element, target)))
    },
    append(child) { element.children.push(child) },
    replaceChildren(...nodes) { element.children = [...nodes] },
    focus() { element.focused = true },
    reset() { element.value = '' },
    setAttribute(name, value) { element.attributes[name] = value },
  }
  Object.defineProperty(element, 'innerHTML', {
    get() { return '' },
    set(value) {
      element.innerHTMLWrites++
      throw new Error(`support 页面不应使用 innerHTML：${value}`)
    },
  })
  return element
}

const tick = () => new Promise(resolve => setImmediate(resolve))
async function flush(times = 6) { for (let index = 0; index < times; index++) await tick() }

function createHarness() {
  const elements = new Map()
  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, createElement(id))
      return elements.get(id)
    },
    createElement(tag) { return createElement(tag) },
  }
  const storageListeners = []
  const chrome = {
    runtime: { getManifest: () => ({ version: '1.0.3' }) },
    storage: { onChanged: { addListener(fn) { storageListeners.push(fn) } } },
  }
  const calls = []
  let respond = async () => ({ success: true, data: {} })
  const exportMessage = async (type, payload) => {
    calls.push({ type, payload: payload === undefined ? undefined : JSON.parse(JSON.stringify(payload)) })
    return respond(type, payload, calls.length - 1)
  }
  const exports = {}
  vm.runInNewContext(code, {
    exports,
    require(name) {
      if (name === './support.css') return {}
      if (name === '../utils/export-flow') return { exportMessage }
      throw new Error(`Unexpected import: ${name}`)
    },
    chrome,
    document,
    console,
    setTimeout,
    clearTimeout,
  })
  return {
    document,
    elements,
    storageListeners,
    calls,
    element: id => document.getElementById(id),
    setRespond(handler) { respond = handler },
  }
}

test('帮助页初始化版本并挂载交互脚本，不发起任何网络请求', () => {
  const harness = createHarness()
  assert.equal(harness.element('version').textContent, 'v 1.0.3')
  assert.equal(harness.calls.length, 0)
})

test('输入内容实时更新 500 字计数', async () => {
  const harness = createHarness()
  const content = harness.element('content')
  content.value = '排版问题'
  await content.dispatch('input')
  assert.equal(harness.element('content-count').textContent, '4 / 500')
})

test('空内容提交只提示，不发送消息', async () => {
  const harness = createHarness()
  await harness.element('feedback-form').dispatch('submit')
  assert.equal(harness.element('submit-status').textContent, '请填写反馈内容')
  assert.equal(harness.element('content').focused, true)
  assert.equal(harness.calls.length, 0)
})

test('提交只带类型、内容和联系方式，并在请求期间禁用重复操作', async () => {
  const harness = createHarness()
  let finish
  harness.setRespond(() => new Promise(resolve => { finish = resolve }))
  const content = harness.element('content')
  content.value = '  排版后页脚错位  '
  harness.element('contact').value = ''
  harness.element('feedback-type').value = 'bug'

  const pending = harness.element('feedback-form').dispatch('submit')
  await flush(2)
  assert.equal(harness.calls.length, 1)
  assert.deepEqual(harness.calls[0], {
    type: 'SUBMIT_FEEDBACK',
    payload: { feedbackType: 'bug', content: '  排版后页脚错位  ', contact: '' },
  })
  assert.equal(harness.element('submit').disabled, true)
  assert.equal(harness.element('content').disabled, true)
  assert.equal(harness.element('contact').disabled, true)
  assert.equal(harness.element('feedback-type').disabled, true)
  assert.match(harness.element('submit-status').textContent, /正在提交/)

  finish({ success: true, data: { anonymous: true } })
  await pending
  assert.equal(harness.element('submit').disabled, false)
  assert.equal(harness.element('content').disabled, false)
  assert.equal(harness.element('feedback-type').disabled, false)
  assert.match(harness.element('submit-status').textContent, /匿名反馈已提交/)
  assert.equal(harness.element('content-count').textContent, '0 / 500')
})

test('登录提交提示可直接在下方查看回复', async () => {
  const harness = createHarness()
  harness.setRespond(async () => ({ success: true, data: { anonymous: false } }))
  harness.element('content').value = '建议增加夜间模式'
  harness.element('feedback-type').value = 'feature_request'
  await harness.element('feedback-form').dispatch('submit')
  assert.match(harness.element('submit-status').textContent, /可在下方“我的反馈”查看处理回复/)
})

test('提交期间账户变化时提示记录归属，避免误认为写入新账号', async () => {
  const harness = createHarness()
  harness.setRespond(async () => ({ success: true, data: { anonymous: false, accountChanged: true } }))
  harness.element('content').value = '切换账号后提交'
  await harness.element('feedback-form').dispatch('submit')
  assert.match(harness.element('submit-status').textContent, /账户已变化/)
  assert.match(harness.element('submit-status').textContent, /归提交时的账号/)
})

test('提交失败保留输入内容并允许重试', async () => {
  const harness = createHarness()
  harness.setRespond(async () => { throw new Error('网络错误') })
  const content = harness.element('content')
  content.value = '点击提交后无反应'
  await harness.element('feedback-form').dispatch('submit')
  assert.equal(content.value, '点击提交后无反应')
  assert.match(harness.element('submit-status').textContent, /^网络错误。内容已保留/)
  assert.equal(harness.element('submit').disabled, false)
  assert.match(harness.element('submit-status').textContent, /避免重复提交/)
})

test('历史记录用 textContent 渲染服务端内容，恶意 HTML 不会执行', async () => {
  const harness = createHarness()
  const malicious = '<img src=x onerror="alert(1)"><script>alert(2)</script>'
  harness.setRespond(async (type) => {
    assert.equal(type, 'LIST_FEEDBACK')
    return {
      success: true,
      data: {
        items: [
          { status: 'pending', created_time: '2026-11-01 10:00', content: malicious, reply_content: '<b>已收到</b>' },
          { status: 'resolved', created_time: '2026-10-30 09:00', content: '普通内容', reply_content: '' },
        ],
        total: 2,
      },
    }
  })

  await harness.element('load-history').dispatch('click')
  await flush()

  const list = harness.element('history-list')
  assert.equal(list.children.length, 2)
  const first = list.children[0]
  assert.equal(first.tagName, 'ARTICLE')
  assert.equal(first.children.length, 3)
  assert.equal(first.children[0].textContent, '待处理 · 2026-11-01 10:00')
  assert.equal(first.children[1].textContent, malicious)
  assert.equal(first.children[2].textContent, '处理回复：<b>已收到</b>')
  assert.equal(first.children[2].className, 'reply')
  assert.equal(list.children[1].children[2].textContent, '暂无处理回复')
  assert.equal(list.children[0].children[1].innerHTMLWrites, 0)
  assert.equal(harness.element('history-status').textContent, '共 2 条反馈')
  assert.equal(harness.element('page-label').textContent, '第 1 页')
  assert.equal(harness.element('previous').disabled, true)
  assert.equal(harness.element('next').disabled, true)
  assert.deepEqual(harness.calls.at(-1), { type: 'LIST_FEEDBACK', payload: { page: 1 } })
})

test('分页按钮按总数翻页，并正确禁用边界', async () => {
  const harness = createHarness()
  const pageItems = count => Array.from({ length: count }, (_, index) => ({
    status: 'processing', created_time: `t${index}`, content: `记录${index}`,
  }))
  harness.setRespond(async (_type, payload) => ({
    success: true,
    data: { items: pageItems(payload.page === 3 ? 5 : 10), total: 25 },
  }))

  await harness.element('load-history').dispatch('click')
  await flush()
  assert.deepEqual(harness.calls.at(-1).payload, { page: 1 })
  assert.equal(harness.element('page-label').textContent, '第 1 页')
  assert.equal(harness.element('previous').disabled, true)
  assert.equal(harness.element('next').disabled, false)

  await harness.element('next').dispatch('click')
  await flush()
  assert.deepEqual(harness.calls.at(-1).payload, { page: 2 })
  assert.equal(harness.element('page-label').textContent, '第 2 页')
  assert.equal(harness.element('previous').disabled, false)
  assert.equal(harness.element('next').disabled, false)

  await harness.element('next').dispatch('click')
  await flush()
  assert.deepEqual(harness.calls.at(-1).payload, { page: 3 })
  assert.equal(harness.element('page-label').textContent, '第 3 页')
  assert.equal(harness.element('previous').disabled, false)
  assert.equal(harness.element('next').disabled, true)
})

test('账户变化后迟到的历史响应不覆盖新状态', async () => {
  const harness = createHarness()
  const first = { resolve: null }
  const second = { resolve: null }
  harness.setRespond((_type, _payload, index) => new Promise(resolve => {
    if (index === 0) first.resolve = resolve
    else second.resolve = resolve
  }))

  harness.element('load-history').dispatch('click')
  await flush(2)
  assert.equal(harness.element('history-list').children.length, 0)
  assert.equal(harness.element('history-status').textContent, '正在加载…')

  harness.storageListeners[0]({ fba_auth_user: { newValue: { nickname: '新账号' } } }, 'local')
  assert.equal(harness.element('history-status').textContent, '账户信息已变化，请重新加载反馈记录')

  harness.element('load-history').dispatch('click')
  await flush(2)
  second.resolve({ success: true, data: { items: [{ status: 'resolved', content: '新记录' }], total: 1 } })
  await flush()
  assert.equal(harness.element('history-list').children[0].children[1].textContent, '新记录')

  first.resolve({ success: true, data: { items: [{ status: 'pending', content: '旧账号迟到记录' }], total: 1 } })
  await flush()
  assert.equal(harness.element('history-list').children.length, 1)
  assert.equal(harness.element('history-list').children[0].children[1].textContent, '新记录')
  assert.equal(harness.element('history-status').textContent, '共 1 条反馈')
})

test('历史读取失败提示错误并保留重试入口', async () => {
  const harness = createHarness()
  harness.setRespond(async () => { throw new Error('请先在插件弹窗登录，再查看反馈记录') })
  await harness.element('load-history').dispatch('click')
  await flush()
  assert.equal(harness.element('history-status').textContent, '请先在插件弹窗登录，再查看反馈记录')
  assert.equal(harness.element('page-label').textContent, '')
  assert.equal(harness.element('load-history').disabled, false)
})

test('账户凭据变化时清空历史并提示重新加载', () => {
  const harness = createHarness()
  const list = harness.element('history-list')
  list.append(createElement('article'))
  harness.storageListeners[0]({ fba_auth_token: { newValue: 'token' } }, 'local')
  assert.equal(list.children.length, 0)
  assert.equal(harness.element('history-status').textContent, '账户信息已变化，请重新加载反馈记录')
  assert.equal(harness.element('load-history').disabled, false)
  assert.equal(harness.element('previous').disabled, true)
  assert.equal(harness.element('next').disabled, true)

  harness.storageListeners[0]({ unrelated: { newValue: 1 } }, 'local')
  assert.equal(harness.element('history-status').textContent, '账户信息已变化，请重新加载反馈记录')
})

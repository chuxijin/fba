import assert from 'node:assert/strict'
import test from 'node:test'
import { importTypeScript } from './helpers/typescript.mjs'

const flow = await importTypeScript(new URL('../src/utils/export-flow.ts', import.meta.url))
const tick = () => new Promise(resolve => setImmediate(resolve))
const files = [{ downloadUrl: '/api/v1/render-books/public/download/vol1', fileName: '卷1.pdf' }]
const delivery = { files, qrCodeUrl: 'http://127.0.0.1:8000/api/v1/render-books/public/minicode/qr1', jobId: 'job-1' }

function messageEnv() {
  const sent = []
  const runtime = { id: 'extension-test' }
  let respond = () => undefined
  runtime.sendMessage = (message, callback) => {
    sent.push(message)
    const action = respond(message, sent.length - 1)
    if (action === 'throw') throw new Error('Extension context invalidated')
    if (action !== undefined) callback(action)
  }
  globalThis.chrome = { runtime }
  return { sent, runtime, setRespond(fn) { respond = fn } }
}

function fakeTimers() {
  const realSetTimeout = globalThis.setTimeout
  const realClearTimeout = globalThis.clearTimeout
  let sequence = 0
  const timers = new Map()
  globalThis.setTimeout = (fn, ms, ...args) => {
    const id = ++sequence
    timers.set(id, { fn, ms, args })
    return id
  }
  globalThis.clearTimeout = (id) => { timers.delete(id) }
  return {
    pending: () => [...timers.values()].map(timer => timer.ms),
    run(ms) {
      for (const [id, timer] of [...timers]) {
        if (timer.ms !== ms) continue
        timers.delete(id)
        timer.fn(...timer.args)
      }
    },
    restore() {
      globalThis.setTimeout = realSetTimeout
      globalThis.clearTimeout = realClearTimeout
    },
  }
}

test('exportMessage 转发消息并在成功响应后清理超时定时器', async (t) => {
  const env = messageEnv()
  const timers = fakeTimers()
  t.after(timers.restore)
  env.setRespond(() => ({ success: true, data: 1 }))
  const response = await flow.exportMessage('GET_RENDER_EXPORT', { ticket: 'ticket' })
  assert.deepEqual(response, { success: true, data: 1 })
  assert.deepEqual(env.sent, [{ type: 'GET_RENDER_EXPORT', payload: { ticket: 'ticket' } }])
  assert.deepEqual(timers.pending(), [])
})

test('exportMessage 在 Chrome lastError、后台失败与同步异常时拒绝', async (t) => {
  const env = messageEnv()
  t.after(() => { delete chrome.runtime.lastError })

  chrome.runtime.lastError = { message: 'The message port closed' }
  env.setRespond(() => ({ success: true }))
  await assert.rejects(flow.exportMessage('X'), error => error.kind === 'communication' && /插件连接暂时中断/.test(error.message))
  delete chrome.runtime.lastError

  env.setRespond(() => ({ success: false, error: '插件通信失败' }))
  await assert.rejects(flow.exportMessage('X'), /插件通信失败/)

  env.setRespond(() => 'throw')
  await assert.rejects(flow.exportMessage('X'), /插件刚刚更新/)
})

test('exportMessage 在后台无响应时按 25 秒超时', async (t) => {
  const env = messageEnv()
  const timers = fakeTimers()
  t.after(timers.restore)
  env.setRespond(() => undefined)
  const pending = flow.exportMessage('GET_RENDER_EXPORT')
  assert.deepEqual(timers.pending(), [25000])
  timers.run(25000)
  await assert.rejects(pending, /插件连接暂时中断/)
})

test('waitForExport 轮询 running 直到 succeeded 并返回交付', async (t) => {
  const env = messageEnv()
  const timers = fakeTimers()
  t.after(timers.restore)
  let polls = 0
  env.setRespond((message) => {
    if (message.type !== 'GET_RENDER_EXPORT') return { success: true }
    polls++
    return polls === 1
      ? { success: true, status: 'running' }
      : { success: true, status: 'succeeded', delivery }
  })

  const pending = flow.waitForExport('ticket-1', () => true)
  await tick()
  assert.deepEqual(timers.pending(), [1500])
  timers.run(1500)
  assert.deepEqual(await pending, delivery)
  assert.equal(polls, 2)
  assert.deepEqual(env.sent.map(message => message.type), ['GET_RENDER_EXPORT', 'GET_RENDER_EXPORT'])
  assert.deepEqual(env.sent[0].payload, { ticket: 'ticket-1' })
})

test('waitForExport 把 failed 状态与异常状态转成可展示错误', async () => {
  const env = messageEnv()
  env.setRespond(() => ({ success: true, status: 'failed', message: '排版失败，请重试' }))
  await assert.rejects(flow.waitForExport('ticket', () => true), /排版失败，请重试/)

  env.setRespond(() => ({ success: true, status: 'queued' }))
  await assert.rejects(flow.waitForExport('ticket', () => true), error => error.kind === 'unknown' && /暂时无法确认/.test(error.message))

  env.setRespond(() => ({ success: false, error: '排版服务响应异常(500)' }))
  await assert.rejects(flow.waitForExport('ticket', () => true), /排版服务响应异常\(500\)/)
})

test('轮询返回后页面已切换时不再展示交付', async () => {
  const env = messageEnv()
  env.setRespond(() => ({ success: true, status: 'running' }))
  let checks = 0
  const isCurrent = () => checks++ === 0
  await assert.rejects(flow.waitForExport('ticket', isCurrent), /已切换页面，本次排版结果不再展示/)
  assert.equal(env.sent.length, 1)
})

test('轮询超过 20 分钟截止时间后停止请求', async (t) => {
  const env = messageEnv()
  const timers = fakeTimers()
  const realNow = Date.now
  const start = 1_700_000_000_000
  const clock = [start, start, start + 20 * 60 * 1000 + 1]
  Date.now = () => clock.length > 1 ? clock.shift() : clock[0]
  t.after(() => {
    timers.restore()
    Date.now = realNow
  })
  env.setRespond(() => ({ success: true, status: 'running' }))

  const pending = flow.waitForExport('ticket', () => true)
  await tick()
  timers.run(1500)
  await assert.rejects(pending, /暂时未能确认排版结果/)
  assert.equal(env.sent.length, 1)
})

test('requestFileDownloads 只提交传入的失败文件并原样返回结果', async () => {
  const env = messageEnv()
  env.setRespond((message) => {
    assert.equal(message.type, 'DOWNLOAD_RENDER_FILES')
    assert.deepEqual(message.payload.files, files)
    return { success: true, savedPath: 'C:/dl/卷1.pdf', failedFiles: [], downloadStarted: true }
  })
  const result = await flow.requestFileDownloads(files)
  assert.deepEqual(result, { success: true, savedPath: 'C:/dl/卷1.pdf', failedFiles: [], downloadStarted: true })
  assert.equal(env.sent.length, 1)
})

test('requestFileDownloads 通信失败时把传入文件全部标记为失败', async () => {
  const env = messageEnv()
  env.setRespond(() => ({ success: false, error: '浏览器下载失败' }))
  const result = await flow.requestFileDownloads(files)
  assert.deepEqual(result.failedFiles, files)
  assert.equal(result.downloadWarning, '浏览器下载失败')
  assert.equal(result.downloadStarted, false)

  env.setRespond(() => 'throw')
  const thrown = await flow.requestFileDownloads(files)
  assert.deepEqual(thrown.failedFiles, files)
  assert.match(thrown.downloadWarning, /插件刚刚更新/)
})

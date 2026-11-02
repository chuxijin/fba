import assert from 'node:assert/strict'
import test from 'node:test'
import { importTypeScript } from './helpers/typescript.mjs'

const flow = await importTypeScript(new URL('../src/utils/export-flow.ts', import.meta.url))
const tick = () => new Promise(resolve => setImmediate(resolve))
const files = [{ downloadUrl: '/api/v1/render-books/public/download/recovery1', fileName: '恢复卷.pdf' }]
const delivery = { files, qrCodeUrl: 'http://127.0.0.1:8000/api/v1/render-books/public/minicode/qr1', jobId: 'job-rec-1' }

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

test('exportMessage 遇到 context invalidated 转换为用户友好的刷新提示', async (t) => {
  const env = messageEnv()
  env.setRespond(() => 'throw')

  await assert.rejects(
    flow.exportMessage('TEST_ACTION', {}),
    (err) => {
      assert.equal(err.kind, 'communication')
      assert.match(err.message, /检测到插件刚刚更新，请按 F5 刷新题库网页/)
      return true
    }
  )
})

test('exportMessage 遇到连接中断转换为友好的防重复排版提示', async (t) => {
  const env = messageEnv()
  chrome.runtime.lastError = { message: 'Could not establish connection. Receiving end does not exist.' }
  t.after(() => { delete chrome.runtime.lastError })

  env.setRespond(() => ({ success: true }))

  await assert.rejects(
    flow.exportMessage('TEST_ACTION', {}),
    (err) => {
      assert.equal(err.kind, 'communication')
      assert.match(err.message, /插件连接暂时中断，排版可能已提交/)
      return true
    }
  )
})

test('waitForExport 遇到 GET 瞬时通信中断时自动重试查询，不重提 POST 或下载', async (t) => {
  const env = messageEnv()
  const timers = fakeTimers()
  t.after(timers.restore)

  let pollCount = 0
  env.setRespond((message) => {
    assert.equal(message.type, 'GET_RENDER_EXPORT')
    assert.deepEqual(message.payload, { ticket: 'ticket-rec-1' })
    pollCount++
    if (pollCount === 1) {
      // 第一次：瞬断 throw
      return 'throw'
    }
    // 第二次重试查询成功并完成交付
    return { success: true, status: 'succeeded', delivery }
  })

  const pending = flow.waitForExport('ticket-rec-1', () => true)
  await tick()

  // 第一次失败触发 sleep(1500)
  assert.deepEqual(timers.pending(), [1500])
  timers.run(1500)

  const result = await pending
  assert.deepEqual(result, delivery)
  assert.equal(pollCount, 2)
  // 所有发送的消息仅为只读的 GET_RENDER_EXPORT，未发起过任何其他 action
  assert.deepEqual(env.sent.map(m => m.type), ['GET_RENDER_EXPORT', 'GET_RENDER_EXPORT'])
})

test('waitForExport 识别 unknown 状态为非 failed 并附带 ticket', async () => {
  const env = messageEnv()
  env.setRespond(() => ({
    success: true,
    status: 'unknown',
    message: '排版处理时间较长或服务已重启，暂时无法确认结果',
  }))

  try {
    await flow.waitForExport('ticket-unknown-1', () => true)
    assert.fail('should have thrown')
  } catch (err) {
    assert.equal(err.kind, 'unknown')
    assert.equal(err.ticket, 'ticket-unknown-1')
    assert.match(err.message, /排版处理时间较长或服务已重启/)
  }
})

test('waitForExport 失败(failed)时携带 ticket，方便上层重试携带 retry_ticket', async () => {
  const env = messageEnv()
  env.setRespond(() => ({
    success: true,
    status: 'failed',
    message: '服务端排版执行失败',
  }))

  try {
    await flow.waitForExport('ticket-fail-1', () => true)
    assert.fail('should have thrown')
  } catch (err) {
    assert.equal(err.kind, 'failed')
    assert.equal(err.ticket, 'ticket-fail-1')
    assert.match(err.message, /服务端排版执行失败/)
  }
})

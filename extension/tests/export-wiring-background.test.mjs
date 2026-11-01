import assert from 'node:assert/strict'
import test from 'node:test'
import { importTypeScript } from './helpers/typescript.mjs'

const data = {}
const messageListeners = []
const storageListeners = []
const downloads = { created: [], searched: [], downloadBehavior: null, searchBehavior: null }
const runtime = {
  onMessage: { addListener(fn) { messageListeners.push(fn) } },
  getURL: path => `chrome-extension://test/${path}`,
  lastError: undefined,
}
const chromeStub = {
  runtime,
  storage: {
    local: {
      async get(keys) {
        if (!keys) return { ...data }
        const list = Array.isArray(keys) ? keys : Object.keys(keys)
        return Object.fromEntries(list.filter(key => key in data).map(key => [key, data[key]]))
      },
      async set(values) { Object.assign(data, values) },
      async remove(keys) {
        for (const key of keys) delete data[key]
      },
    },
    onChanged: { addListener(fn) { storageListeners.push(fn) } },
  },
  tabs: { async query() { return [] }, async sendMessage() {} },
  downloads: {
    download(options, callback) {
      downloads.created.push(options)
      const step = downloads.downloadBehavior?.(options, downloads.created.length - 1) ?? { id: downloads.created.length }
      queueMicrotask(() => {
        if (step.lastError) {
          runtime.lastError = { message: step.lastError }
          callback(undefined)
          delete runtime.lastError
          return
        }
        callback(step.id)
      })
    },
    search(query, callback) {
      downloads.searched.push(query)
      const step = downloads.searchBehavior?.(query, downloads.searched.length - 1) ?? {}
      queueMicrotask(() => {
        if (step.lastError) {
          runtime.lastError = { message: step.lastError }
          callback([])
          delete runtime.lastError
          return
        }
        callback(step.items || [])
      })
    },
  },
}
globalThis.chrome = chromeStub

await importTypeScript(new URL('../src/background/index.ts', import.meta.url))
const onMessage = messageListeners[0]

const realSetTimeout = globalThis.setTimeout
const TICKET = 'b'.repeat(32)
const BACKEND = 'http://127.0.0.1:8000'
const download = (name = 'vol1') => `/api/v1/render-books/public/download/${name}`
const qr = (name = 'qr1') => `/api/v1/render-books/public/minicode/${name}`
const json = (body, status = 200) => new Response(JSON.stringify(body), { status })
const payload = (downloadUrl = download(), fileName = '卷1.pdf') => ({ downloadUrl, fileName })

function reset({ downloadBehavior = null, searchBehavior = null } = {}) {
  for (const key of Object.keys(data)) delete data[key]
  downloads.created.length = 0
  downloads.searched.length = 0
  downloads.downloadBehavior = downloadBehavior
  downloads.searchBehavior = searchBehavior
  runtime.lastError = undefined
}

function send(message, sender = { url: 'chrome-extension://test/content.js', frameId: 0 }) {
  return new Promise((resolve) => { onMessage(message, sender, resolve) })
}

function fastDownloadWait(t) {
  globalThis.setTimeout = (fn, ms, ...args) => {
    if (ms === 1200) {
      queueMicrotask(() => fn(...args))
      return 0
    }
    return realSetTimeout(fn, ms, ...args)
  }
  t.after(() => { globalThis.setTimeout = realSetTimeout })
}

test('后台接收排版请求并返回任务凭证', async () => {
  reset()
  globalThis.fetch = async (url, init) => {
    assert.equal(url, `${BACKEND}/api/v1/render-books/public/exports`)
    assert.equal(init.method, 'POST')
    assert.equal(init.headers.Authorization, undefined)
    const body = JSON.parse(init.body)
    assert.equal(body.target, 'computer_download')
    assert.deepEqual(body.options, { include_answer: true, answer_placement: 'merged', output_format: 'pdf' })
    return json({ code: 200, data: { ticket: TICKET } })
  }
  const response = await send({
    type: 'RENDER_AND_EXPORT',
    payload: {
      paper: { title: '卷', total_questions: 2, sections: [] },
      settings: { includeAnswer: true, answerPlacement: 'merged', outputFormat: 'pdf' },
      target: 'computer_download',
    },
  })
  assert.deepEqual(response, { success: true, ticket: TICKET })
})

test('排版请求失败时真实抛错，不再返回演示交付', async () => {
  reset()
  globalThis.fetch = async () => { throw new Error('Failed to fetch') }
  const response = await send({
    type: 'RENDER_AND_EXPORT',
    payload: { paper: {}, settings: {}, target: 'mobile_sync' },
  })
  assert.equal(response.success, false)
  assert.equal(response.error, 'Failed to fetch')
  assert.equal('ticket' in response, false)
})

test('后端 HTTP 错误与无效凭证都拒绝提交', async () => {
  reset()
  globalThis.fetch = async () => json({ msg: '今日额度已用完' }, 429)
  const quota = await send({
    type: 'RENDER_AND_EXPORT',
    payload: { paper: {}, settings: {}, target: 'computer_download' },
  })
  assert.deepEqual(quota, { success: false, error: '今日额度已用完' })

  globalThis.fetch = async () => json({ code: 200, data: { ticket: 'short' } })
  const invalid = await send({
    type: 'RENDER_AND_EXPORT',
    payload: { paper: {}, settings: {}, target: 'computer_download' },
  })
  assert.deepEqual(invalid, { success: false, error: '排版服务未返回任务凭证' })
})

test('轮询凭证格式非法时同步拒绝且不再请求后端', async () => {
  reset()
  let fetched = 0
  globalThis.fetch = async () => { fetched++; return json({ code: 200, data: {} }) }
  let response
  const returned = onMessage({ type: 'GET_RENDER_EXPORT', payload: { ticket: 'bad' } }, {}, value => { response = value })
  assert.equal(returned, false)
  assert.deepEqual(response, { success: false, error: '排版任务凭证无效' })
  assert.equal(fetched, 0)
})

test('轮询 running 不产生交付', async () => {
  reset()
  globalThis.fetch = async (url) => {
    assert.equal(url, `${BACKEND}/api/v1/render-books/public/exports/${TICKET}`)
    return json({ code: 200, data: { status: 'running' } })
  }
  const response = await send({ type: 'GET_RENDER_EXPORT', payload: { ticket: TICKET } })
  assert.deepEqual(response, { success: true, status: 'running' })
  assert.equal(response.delivery, undefined)
})

test('轮询成功后解析主册、分册与二维码并刷新额度提示', async () => {
  reset()
  globalThis.fetch = async () => json({
    code: 200,
    data: {
      status: 'succeeded',
      result: {
        download_url: download('vol1'),
        file_name: '卷1.pdf',
        qr_code_url: qr('qr1'),
        job_id: 'job-1',
        remaining_quota: 2,
        extra_files: [{ download_url: download('vol2'), file_name: '卷2.pdf' }],
      },
    },
  })
  const response = await send({ type: 'GET_RENDER_EXPORT', payload: { ticket: TICKET } })
  assert.equal(response.success, true)
  assert.equal(response.status, 'succeeded')
  assert.deepEqual(response.delivery.files, [
    { downloadUrl: `${BACKEND}${download('vol1')}`, fileName: '卷1.pdf' },
    { downloadUrl: `${BACKEND}${download('vol2')}`, fileName: '卷2.pdf' },
  ])
  assert.equal(response.delivery.qrCodeUrl, `${BACKEND}${qr('qr1')}`)
  assert.equal(response.delivery.jobId, 'job-1')
  assert.equal(response.delivery.remainingQuota, 2)
  assert.equal(typeof data.fba_quota_revision, 'string')
})

test('轮询完成但交付地址被拒绝时返回错误', async () => {
  reset()
  globalThis.fetch = async () => json({
    code: 200,
    data: {
      status: 'succeeded',
      result: {
        download_url: 'https://evil.test/api/v1/render-books/public/download/vol1',
        file_name: '卷1.pdf',
        qr_code_url: qr('qr1'),
        job_id: 'job-1',
      },
    },
  })
  const response = await send({ type: 'GET_RENDER_EXPORT', payload: { ticket: TICKET } })
  assert.deepEqual(response, { success: false, error: '排版服务返回了无效的交付地址' })
})

test('轮询失败状态与后端异常都回传明确错误', async () => {
  reset()
  globalThis.fetch = async () => json({ code: 200, data: { status: 'failed', message: '渲染引擎异常' } })
  assert.deepEqual(await send({ type: 'GET_RENDER_EXPORT', payload: { ticket: TICKET } }), {
    success: true, status: 'failed', message: '渲染引擎异常',
  })

  globalThis.fetch = async () => json({ code: 404, msg: '任务不存在' }, 404)
  assert.deepEqual(await send({ type: 'GET_RENDER_EXPORT', payload: { ticket: TICKET } }), {
    success: false,
    error: '任务不存在',
  })

  globalThis.fetch = async () => json({ code: 404, msg: 'Not Found' }, 404)
  assert.deepEqual(await send({ type: 'GET_RENDER_EXPORT', payload: { ticket: TICKET } }), {
    success: false,
    error: '排版服务尚未就绪，请联系维护者确认服务版本；不要重复提交',
  })
})

test('二维码读取成功与独立失败互不影响排版交付', async () => {
  reset()
  globalThis.fetch = async (url) => {
    if (url.endsWith('/exports')) {
      return json({
        code: 200,
        data: {
          status: 'succeeded',
          result: { download_url: download('vol1'), file_name: '卷1.pdf', qr_code_url: qr('qr1'), job_id: 'job-1' },
        },
      })
    }
    if (url.endsWith(`/exports/${TICKET}`)) {
      return json({ code: 200, data: { status: 'running' } })
    }
    if (url.includes('/minicode/')) {
      return new Response(new Uint8Array([137, 80, 78, 71]), { headers: { 'content-type': 'image/png' } })
    }
  }

  const qrResponse = await send({ type: 'GET_RENDER_QR', payload: { url: qr('qr1') } })
  assert.equal(qrResponse.success, true)
  assert.match(qrResponse.image, /^data:image\/png;base64,/)

  const delivery = await send({ type: 'GET_RENDER_EXPORT', payload: { ticket: TICKET } })
  assert.equal(delivery.success, true)

  globalThis.fetch = async () => new Response('missing', { status: 404 })
  const failedQr = await send({ type: 'GET_RENDER_QR', payload: { url: qr('qr2') } })
  assert.deepEqual(failedQr, { success: false, error: '小程序码暂时不可用，请稍后重试' })
})

test('两册下载经后台完成并返回首个保存路径', async (t) => {
  fastDownloadWait(t)
  reset({ searchBehavior: () => ({ items: [{ state: 'complete', filename: 'C:/dl/file.pdf' }] }) })
  const response = await send({
    type: 'DOWNLOAD_RENDER_FILES',
    payload: { files: [payload(download('vol1'), '卷1.pdf'), payload(download('vol2'), '卷2.pdf')] },
  })
  assert.equal(downloads.created.length, 2)
  assert.equal(response.success, true)
  assert.equal(response.savedPath, 'C:/dl/file.pdf')
  assert.deepEqual(response.failedFiles, [])
  assert.equal(response.downloadWarning, '')
  assert.equal(response.downloadStarted, true)
})

test('Chrome lastError 只影响对应文件，保留可重试失败列表', async (t) => {
  fastDownloadWait(t)
  reset({
    downloadBehavior: options => options.filename === '卷2.pdf' ? { lastError: 'DENIED' } : { id: 5 },
    searchBehavior: () => ({ items: [{ state: 'complete', filename: 'C:/dl/卷1.pdf' }] }),
  })
  const good = payload(download('vol1'), '卷1.pdf')
  const bad = payload(download('vol2'), '卷2.pdf')
  const response = await send({ type: 'DOWNLOAD_RENDER_FILES', payload: { files: [good, bad] } })
  assert.deepEqual(response.failedFiles, [bad])
  assert.match(response.downloadWarning, /卷2\.pdf：DENIED/)
  assert.equal(response.downloadStarted, true)
  assert.equal(response.savedPath, 'C:/dl/卷1.pdf')
})

test('浏览器无下载记录与下载中断都标记为可重试失败', async (t) => {
  fastDownloadWait(t)
  reset({
    downloadBehavior: () => ({ id: 3 }),
    searchBehavior: () => ({ items: [] }),
  })
  const noRecord = await send({ type: 'DOWNLOAD_RENDER_FILES', payload: { files: [payload()] } })
  assert.equal(noRecord.success, true)
  assert.equal(noRecord.failedFiles.length, 1)
  assert.match(noRecord.downloadWarning, /浏览器下载记录不可用，请打开下载列表确认/)
  assert.equal(noRecord.downloadStarted, false)

  reset({
    downloadBehavior: () => ({ id: 4 }),
    searchBehavior: () => ({ items: [{ state: 'interrupted', error: 'NETWORK_FAILED' }] }),
  })
  const interrupted = await send({ type: 'DOWNLOAD_RENDER_FILES', payload: { files: [payload()] } })
  assert.equal(interrupted.success, true)
  assert.equal(interrupted.failedFiles.length, 1)
  assert.match(interrupted.downloadWarning, /浏览器下载中断：NETWORK_FAILED/)
})

test('非法文件列表与恶意地址在创建下载前被拦截', async (t) => {
  fastDownloadWait(t)
  reset()

  const empty = await send({ type: 'DOWNLOAD_RENDER_FILES', payload: { files: [] } })
  assert.deepEqual(empty, { success: false, error: '下载文件列表无效' })

  const rejected = await send({
    type: 'DOWNLOAD_RENDER_FILES',
    payload: {
      files: [
        payload(),
        { downloadUrl: 'https://evil.test/api/v1/render-books/public/download/vol2', fileName: '卷2.pdf' },
      ],
    },
  })
  assert.deepEqual(rejected, { success: false, error: '排版服务返回了无效的交付地址' })
  assert.equal(downloads.created.length, 0)
})

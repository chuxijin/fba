import assert from 'node:assert/strict'
import test from 'node:test'
import { importTypeScript } from './helpers/typescript.mjs'

const delivery = await importTypeScript(new URL('../src/utils/export-delivery.ts', import.meta.url))
const { BACKEND_BASE } = await importTypeScript(new URL('../src/utils/auth-protocol.ts', import.meta.url))

const realSetTimeout = globalThis.setTimeout
const downloadUrl = (name = 'vol1') => `/api/v1/render-books/public/download/${name}`
const qrUrl = (name = 'qr1') => `/api/v1/render-books/public/minicode/${name}`
const absolute = (raw) => new URL(raw, `${BACKEND_BASE}/`).href

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

function downloadsEnv(behavior = {}) {
  const created = []
  const searched = []
  const runtime = {}
  let nextId = 0
  globalThis.chrome = {
    runtime,
    downloads: {
      download(options, callback) {
        created.push(options)
        const step = behavior.download?.(options, created.length - 1) ?? { id: ++nextId }
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
        searched.push(query)
        const step = behavior.search?.(query, searched.length - 1) ?? {}
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
  return { created, searched }
}

test('交付地址只接受后端公开下载与小程序码路径', () => {
  assert.equal(delivery.exportUrl(downloadUrl(), 'download'), absolute(downloadUrl()))
  assert.equal(delivery.exportUrl(absolute(qrUrl('qr_2')), 'minicode'), absolute(qrUrl('qr_2')))
  assert.equal(delivery.exportUrl(downloadUrl('A_z-9'), 'download'), absolute(downloadUrl('A_z-9')))
})

test('跨域、凭据、查询串、哈希与非白名单路径全部拒绝', () => {
  const rejected = [
    'https://evil.test/api/v1/render-books/public/download/vol1',
    '//evil.test/api/v1/render-books/public/download/vol1',
    'http://user:pass@127.0.0.1:8000/api/v1/render-books/public/download/vol1',
    `${downloadUrl()}?token=1`,
    `${downloadUrl()}#fragment`,
    '/api/v1/render-books/public/download/vol1/extra',
    '/api/v1/render-books/public/download/vol1.pdf',
    '/api/v1/render-books/public/download/',
    '/api/v1/render-books/public/other/vol1',
    '/api/v1/render-books/public/download/../minicode/qr1',
    'javascript:alert(1)',
    '',
  ]
  for (const raw of rejected) assert.throws(() => delivery.exportUrl(raw, 'download'), /无效的交付地址/, raw)
})

test('parseDelivery 同时接受主册与分册，并解析二维码和剩余额度', () => {
  const parsed = delivery.parseDelivery({
    download_url: downloadUrl('vol1'),
    file_name: '卷1.pdf',
    qr_code_url: qrUrl('qr1'),
    job_id: 'job-1',
    remaining_quota: 2,
    extra_files: [{ download_url: downloadUrl('vol2'), file_name: '卷2.pdf' }],
  })
  assert.deepEqual(parsed, {
    files: [
      { downloadUrl: absolute(downloadUrl('vol1')), fileName: '卷1.pdf' },
      { downloadUrl: absolute(downloadUrl('vol2')), fileName: '卷2.pdf' },
    ],
    qrCodeUrl: absolute(qrUrl('qr1')),
    jobId: 'job-1',
    remainingQuota: 2,
  })
})

test('parseDelivery 拒绝不完整的交付信息与分册', () => {
  const complete = {
    download_url: downloadUrl(),
    file_name: '卷1.pdf',
    qr_code_url: qrUrl(),
    job_id: 'job-1',
  }
  for (const key of ['download_url', 'file_name', 'qr_code_url', 'job_id']) {
    const result = { ...complete }
    delete result[key]
    assert.throws(() => delivery.parseDelivery(result), /排版服务未返回完整交付信息/, key)
  }
  assert.throws(() => delivery.parseDelivery({
    ...complete,
    extra_files: [{ download_url: downloadUrl('vol2') }],
  }), /分册交付信息不完整/)
  assert.throws(() => delivery.parseDelivery({
    ...complete,
    extra_files: [{ download_url: 'https://evil.test/api/v1/render-books/public/download/vol2', file_name: '卷2.pdf' }],
  }), /无效的交付地址/)
  assert.throws(() => delivery.parseDelivery({ ...complete, download_url: 'https://evil.test/download/vol1' }), /无效的交付地址/)
})

test('exportUrl 空值与非对象交付不会放行', () => {
  assert.throws(() => delivery.parseDelivery(null), /排版服务未返回完整交付信息/)
  assert.throws(() => delivery.parseDelivery({}), /排版服务未返回完整交付信息/)
})

test('sanitizeFileName 清理非法字符、首尾空白并保留兜底名', () => {
  assert.equal(delivery.sanitizeFileName('  ..卷/1:2*3?4"5<6>7|8\r\n\t.pdf..  '), '卷_1_2_3_4_5_6_7_8___.pdf')
  assert.equal(delivery.sanitizeFileName(''), '未命名试卷.pdf')
  assert.equal(delivery.sanitizeFileName('   ...   '), '未命名试卷.pdf')
  assert.equal(delivery.sanitizeFileName('a'.repeat(300)).length, 180)
})

test('sanitizeFileName 超长 pdf/docx 截断后仍保留原后缀', () => {
  const pdf = delivery.sanitizeFileName(`${'甲'.repeat(300)}.pdf`)
  assert.equal(pdf.length, 180)
  assert.equal(pdf, `${'甲'.repeat(176)}.pdf`)

  const docx = delivery.sanitizeFileName(`${'乙'.repeat(300)}.DOCX`)
  assert.equal(docx.length, 180)
  assert.equal(docx, `${'乙'.repeat(175)}.DOCX`)

  const messy = delivery.sanitizeFileName(`  ${'卷/题:'.repeat(80)}.docx...  `)
  assert.equal(messy.length, 180)
  assert.match(messy, /\.docx$/)

  const boundary = `${'a'.repeat(176)}.pdf`
  assert.equal(delivery.sanitizeFileName(boundary), boundary)
  assert.equal(delivery.sanitizeFileName(`${'a'.repeat(177)}.pdf`).length, 180)
})

test('小程序码读取 PNG 并转成 data URL', async () => {
  globalThis.fetch = async (url, init) => {
    assert.equal(url, absolute(qrUrl()))
    assert.ok(init.signal)
    return new Response(new Uint8Array([137, 80, 78, 71]), {
      headers: { 'content-type': 'image/png; charset=binary' },
    })
  }
  const image = await delivery.fetchExportQr(qrUrl())
  assert.match(image, /^data:image\/png;base64,/)
})

test('小程序码内容类型不符、HTTP 失败与网络异常都单独报错', async () => {
  globalThis.fetch = async () => new Response('<html>', { headers: { 'content-type': 'text/html' } })
  await assert.rejects(delivery.fetchExportQr(qrUrl()), /小程序码暂时不可用，请稍后重试/)
  globalThis.fetch = async () => new Response('missing', { status: 404, headers: { 'content-type': 'image/png' } })
  await assert.rejects(delivery.fetchExportQr(qrUrl()), /小程序码暂时不可用，请稍后重试/)
  globalThis.fetch = async () => { throw new Error('offline') }
  await assert.rejects(delivery.fetchExportQr(qrUrl()), /offline/)
})

test('exportRequest 解包 data，业务错误与网络错误分别抛出', async () => {
  globalThis.fetch = async (url, init) => {
    assert.equal(url, `${BACKEND_BASE}/api/v1/render-books/public/exports/ticket`)
    assert.ok(init.signal)
    return new Response(JSON.stringify({ code: 200, data: { status: 'running' } }), { status: 200 })
  }
  assert.deepEqual(await delivery.exportRequest('/exports/ticket'), { status: 'running' })

  globalThis.fetch = async () => new Response(JSON.stringify({ code: 500, msg: '任务不存在' }), { status: 500 })
  await assert.rejects(delivery.exportRequest('/exports/ticket'), /任务不存在/)

  globalThis.fetch = async () => new Response('gateway down', { status: 502 })
  await assert.rejects(delivery.exportRequest('/exports/ticket'), /排版服务响应异常\(502\)/)
})

test('exportRequest 404 保留后端具体提示，通用 404 提示服务未就绪', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ code: 404, msg: '任务不存在' }), { status: 404 })
  await assert.rejects(delivery.exportRequest('/exports/ticket'), /任务不存在/)

  const genericBodies = [
    JSON.stringify({ code: 404, msg: 'Not Found' }),
    JSON.stringify({ code: 404, msg: '请求错误' }),
    '<html>not found</html>',
  ]
  for (const body of genericBodies) {
    globalThis.fetch = async () => new Response(body, { status: 404 })
    await assert.rejects(
      delivery.exportRequest('/exports/ticket'),
      /排版服务尚未就绪，请联系维护者确认服务版本；不要重复提交/,
      body,
    )
  }
})

test('downloadExportFile 创建下载并返回浏览器保存路径', async (t) => {
  fastDownloadWait(t)
  const env = downloadsEnv({
    download: () => ({ id: 42 }),
    search: () => ({ items: [{ state: 'complete', filename: 'C:/dl/a.pdf' }] }),
  })
  const saved = await delivery.downloadExportFile({ downloadUrl: downloadUrl('a'), fileName: 'a.pdf' })
  assert.equal(saved, 'C:/dl/a.pdf')
  assert.equal(env.created.length, 1)
  assert.equal(env.created[0].url, absolute(downloadUrl('a')))
  assert.equal(env.created[0].filename, 'a.pdf')
  assert.equal(env.created[0].saveAs, false)
  assert.deepEqual(env.searched, [{ id: 42 }])
})

test('Chrome lastError 与未创建任务都算下载失败', async (t) => {
  fastDownloadWait(t)
  downloadsEnv({ download: () => ({ lastError: 'Invalid URL' }) })
  await assert.rejects(
    delivery.downloadExportFile({ downloadUrl: downloadUrl('a'), fileName: 'a.pdf' }),
    /Invalid URL/,
  )

  downloadsEnv({ download: () => ({}) })
  await assert.rejects(
    delivery.downloadExportFile({ downloadUrl: downloadUrl('a'), fileName: 'a.pdf' }),
    /浏览器未创建下载任务/,
  )
})

test('无下载记录、查询失败与中断分别给出可恢复提示', async (t) => {
  fastDownloadWait(t)
  downloadsEnv({ download: () => ({ id: 1 }), search: () => ({ items: [] }) })
  await assert.rejects(
    delivery.downloadExportFile({ downloadUrl: downloadUrl('a'), fileName: 'a.pdf' }),
    /浏览器下载记录不可用，请打开下载列表确认/,
  )

  downloadsEnv({ download: () => ({ id: 1 }), search: () => ({ lastError: '无法读取下载状态' }) })
  await assert.rejects(
    delivery.downloadExportFile({ downloadUrl: downloadUrl('a'), fileName: 'a.pdf' }),
    /无法读取下载状态/,
  )

  downloadsEnv({
    download: () => ({ id: 1 }),
    search: () => ({ items: [{ state: 'interrupted', error: 'NETWORK_FAILED' }] }),
  })
  await assert.rejects(
    delivery.downloadExportFile({ downloadUrl: downloadUrl('a'), fileName: 'a.pdf' }),
    /浏览器下载中断：NETWORK_FAILED，可重试下载，无需重新排版/,
  )
})

test('两个分册依次下载，保存首个成功路径且无失败项', async (t) => {
  fastDownloadWait(t)
  const env = downloadsEnv({
    search: (query) => ({ items: [{ state: 'complete', filename: `C:/dl/${query.id}.pdf` }] }),
  })
  const files = [
    { downloadUrl: downloadUrl('vol1'), fileName: '卷1.pdf' },
    { downloadUrl: downloadUrl('vol2'), fileName: '卷2.pdf' },
  ]
  const result = await delivery.downloadExportFiles(files)
  assert.equal(env.created.length, 2)
  assert.equal(env.created[0].filename, '卷1.pdf')
  assert.equal(env.created[1].filename, '卷2.pdf')
  assert.equal(result.savedPath, 'C:/dl/1.pdf')
  assert.deepEqual(result.failedFiles, [])
  assert.equal(result.downloadWarning, '')
  assert.equal(result.downloadStarted, true)
})

test('单个分册失败不阻断另一个，失败列表只保留失败文件', async (t) => {
  fastDownloadWait(t)
  downloadsEnv({
    download: (options) => options.filename === '卷2.pdf' ? { lastError: 'DENIED' } : { id: 7 },
    search: () => ({ items: [{ state: 'complete', filename: 'C:/dl/卷1.pdf' }] }),
  })
  const good = { downloadUrl: downloadUrl('vol1'), fileName: '卷1.pdf' }
  const bad = { downloadUrl: downloadUrl('vol2'), fileName: '卷2.pdf' }
  const result = await delivery.downloadExportFiles([good, bad])
  assert.equal(result.savedPath, 'C:/dl/卷1.pdf')
  assert.deepEqual(result.failedFiles, [bad])
  assert.match(result.downloadWarning, /卷2\.pdf：DENIED/)
  assert.equal(result.downloadStarted, true)
})

test('全部失败时 downloadStarted 为 false 且保留每个失败原因', async (t) => {
  fastDownloadWait(t)
  downloadsEnv({ download: () => ({ lastError: 'DENIED' }) })
  const files = [
    { downloadUrl: downloadUrl('vol1'), fileName: '卷1.pdf' },
    { downloadUrl: downloadUrl('vol2'), fileName: '卷2.pdf' },
  ]
  const result = await delivery.downloadExportFiles(files)
  assert.deepEqual(result.failedFiles, files)
  assert.equal(result.downloadStarted, false)
  assert.match(result.downloadWarning, /卷1\.pdf：DENIED；卷2\.pdf：DENIED/)
})

test('文件列表非法或含恶意地址时不会产生任何下载副作用', async (t) => {
  fastDownloadWait(t)
  const env = downloadsEnv()
  const good = { downloadUrl: downloadUrl('vol1'), fileName: '卷1.pdf' }
  await assert.rejects(delivery.downloadExportFiles([]), /下载文件列表无效/)
  await assert.rejects(delivery.downloadExportFiles([good, good, good]), /下载文件列表无效/)
  await assert.rejects(delivery.downloadExportFiles([
    good,
    { downloadUrl: 'https://evil.test/api/v1/render-books/public/download/vol2', fileName: '卷2.pdf' },
  ]), /无效的交付地址/)
  assert.equal(env.created.length, 0)
})

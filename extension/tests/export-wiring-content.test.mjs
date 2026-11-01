import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'
import { compileSource, importTypeScript } from './helpers/typescript.mjs'

const contentCode = compileSource(await readFile(new URL('../src/content/index.ts', import.meta.url), 'utf8'))
const exportFlow = await importTypeScript(new URL('../src/utils/export-flow.ts', import.meta.url))

const PAGE = 'https://spa.fenbi.com/ti/exam/solution/1_2_report'
const TICKET = 'a'.repeat(32)
const PAPER = { title: '模考卷', total_questions: 10, sections: [], metadata: {} }
const SETTINGS = { includeAnswer: true, answerPlacement: 'merged', outputFormat: 'pdf', exportScope: 'all' }
const tick = () => new Promise(resolve => setImmediate(resolve))

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

function createHarness({ paper = PAPER, href = PAGE, respond } = {}) {
  const events = []
  const sent = []
  let handlers = null
  const window = new EventTarget()
  window.postMessage = () => {}
  const document = new EventTarget()
  Object.assign(document, { readyState: 'complete', body: null })
  const location = { href, origin: new URL(href).origin }
  const runtime = {
    id: 'extension-test',
    onMessage: { addListener() {} },
    sendMessage(message, callback) {
      sent.push(message)
      queueMicrotask(() => {
        const response = respond?.(message, { location, sent })
        if (response !== undefined) callback(response)
      })
    },
  }
  const chrome = { runtime }
  globalThis.chrome = chrome
  const ui = {
    setPaper() {},
    setPaperInfo() {},
    setImportState() {},
    setReportDraft() {},
    setReportStatus() {},
    resetPaper() {},
    openModal() {},
    closeModal() {},
    showLoading(target) { events.push({ type: 'loading', target }) },
    showDelivery(view) { events.push({ type: 'delivery', view }) },
    showError(message) { events.push({ type: 'error', message }) },
  }
  const adapters = {
    DEFAULT_TYPOGRAPHY_SETTINGS: SETTINGS,
    IDLE_IMPORT_STATE: {},
    adaptFenbiPaper: () => paper,
    adaptHuatuPaper: () => paper,
    adaptShikaobangPaper: () => paper,
    fetchFenbiPaperActively: async () => null,
    fetchHuatuPaperActively: async () => null,
    fetchShikaobangPaperActively: async () => null,
    extractFenbiPaperFromDom: () => null,
    extractHuatuPaperFromDom: () => null,
    extractShikaobangPaperFromDom: () => null,
    fetchMistakeQuestionsByCount: async () => null,
    parseMistakePageMeta: () => null,
    backfillPaperAnswers: async value => value,
    setCachedKeypointTree() {},
    fenbiSession: {
      getPaper: () => paper,
      handleNetworkPayload: () => paper,
      enrichFromDom: value => value,
      reset() {},
    },
    buildWrongImportItems: () => ({ items: [], skipped: 0 }),
  }
  const modules = {
    '../adapters': adapters,
    './ui/mount': { mountReformatterApp(value) { handlers = value; return ui } },
    '../adapters/fenbi/report': {
      buildFenbiPracticeQuestions: () => [],
      buildFenbiPracticeReport: () => ({}),
      buildReportModules: () => [],
      fenbiReportRoute: () => null,
      readFenbiReportModules: () => [],
    },
    '../adapters/fenbi/report-cache': {
      FenbiReportCache: class {
        capture() {}
        read() { return {} }
        reset() {}
      },
    },
    '../utils/export-flow': exportFlow,
  }
  vm.runInNewContext(contentCode, {
    exports: {},
    require(name) {
      if (!(name in modules)) throw new Error(`Unexpected import: ${name}`)
      return modules[name]
    },
    document,
    window,
    location,
    chrome,
    crypto,
    console,
    setTimeout: () => 0,
    setInterval: () => 0,
    clearTimeout() {},
    clearInterval() {},
    queueMicrotask,
  })
  return { events, sent, handlers, ui, location, chrome }
}

function deliveryView() {
  return {
    files: [
      { downloadUrl: '/api/v1/render-books/public/download/vol1', fileName: '卷1.pdf' },
      { downloadUrl: '/api/v1/render-books/public/download/vol2', fileName: '卷2.pdf' },
    ],
    qrCodeUrl: '/api/v1/render-books/public/minicode/qr1',
    jobId: 'job-1',
    remainingQuota: 2,
  }
}

test('电脑下载：提交成功、轮询成功并把两个分册交给后台下载', async (t) => {
  const delivery = deliveryView()
  const download = { success: true, savedPath: 'C:/dl/卷1.pdf', failedFiles: [], downloadWarning: '', downloadStarted: true }
  let polls = 0
  const harness = createHarness({
    respond(message) {
      if (message.type === 'RENDER_AND_EXPORT') return { success: true, ticket: TICKET }
      if (message.type === 'GET_RENDER_EXPORT') {
        polls++
        return polls === 1
          ? { success: true, status: 'running' }
          : { success: true, status: 'succeeded', delivery }
      }
      if (message.type === 'DOWNLOAD_RENDER_FILES') {
        assert.deepEqual(message.payload.files, delivery.files)
        return download
      }
    },
  })
  const timers = fakeTimers()
  t.after(timers.restore)

  const pending = harness.handlers.onDoExport(SETTINGS, 'computer_download')
  await tick()
  assert.deepEqual(timers.pending(), [1500])
  timers.run(1500)
  await pending

  assert.deepEqual(harness.sent.map(message => message.type), [
    'RENDER_AND_EXPORT', 'GET_RENDER_EXPORT', 'GET_RENDER_EXPORT', 'DOWNLOAD_RENDER_FILES',
  ])
  assert.equal(harness.sent[0].payload.target, 'computer_download')
  assert.deepEqual(harness.events[0], { type: 'loading', target: 'computer_download' })
  assert.equal(harness.events.length, 2)
  assert.equal(harness.events[1].type, 'delivery')
  const view = harness.events[1].view
  assert.deepEqual(view.files, delivery.files)
  assert.equal(view.savedPath, 'C:/dl/卷1.pdf')
  assert.deepEqual(view.failedFiles, [])
  assert.equal(view.downloadWarning, '')
  assert.equal(view.downloadStarted, true)
})

test('手机同步：成功交付但不触发浏览器下载', async (t) => {
  const delivery = deliveryView()
  const harness = createHarness({
    respond(message) {
      if (message.type === 'RENDER_AND_EXPORT') return { success: true, ticket: TICKET }
      if (message.type === 'GET_RENDER_EXPORT') return { success: true, status: 'succeeded', delivery }
    },
  })
  const timers = fakeTimers()
  t.after(timers.restore)

  await harness.handlers.onDoExport(SETTINGS, 'mobile_sync')

  assert.deepEqual(harness.sent.map(message => message.type), ['RENDER_AND_EXPORT', 'GET_RENDER_EXPORT'])
  assert.equal(harness.sent[0].payload.target, 'mobile_sync')
  assert.equal(harness.events.at(-1).type, 'delivery')
  assert.equal(harness.events.at(-1).view.savedPath, undefined)
  assert.equal(harness.events.at(-1).view.downloadStarted, undefined)
})

test('轮询 failed 状态进入错误重试视图', async () => {
  const harness = createHarness({
    respond(message) {
      if (message.type === 'RENDER_AND_EXPORT') return { success: true, ticket: TICKET }
      if (message.type === 'GET_RENDER_EXPORT') return { success: true, status: 'failed', message: '排版失败，请重试' }
    },
  })
  await harness.handlers.onDoExport(SETTINGS, 'computer_download')
  assert.deepEqual(harness.events.at(-1), { type: 'error', message: '排版失败，请重试' })
})

test('提交阶段后台失败不会伪造交付', async () => {
  const harness = createHarness({
    respond(message) {
      if (message.type === 'RENDER_AND_EXPORT') return { success: false, error: '排版服务响应异常(500)' }
    },
  })
  await harness.handlers.onDoExport(SETTINGS, 'computer_download')
  assert.deepEqual(harness.events.map(event => event.type), ['loading', 'error'])
  assert.deepEqual(harness.events[1], { type: 'error', message: '排版服务响应异常(500)' })
  assert.equal(harness.sent.length, 1)
})

test('轮询返回前页面已切换则不展示交付也不报错', async () => {
  const harness = createHarness({
    respond(message, { location }) {
      if (message.type === 'RENDER_AND_EXPORT') return { success: true, ticket: TICKET }
      if (message.type === 'GET_RENDER_EXPORT') {
        location.href = 'https://spa.fenbi.com/other'
        return { success: true, status: 'running' }
      }
    },
  })
  await harness.handlers.onDoExport(SETTINGS, 'computer_download')
  assert.deepEqual(harness.events.map(event => event.type), ['loading'])
  assert.equal(harness.sent.length, 2)
})

test('扩展刚更新时拒绝导出并提示刷新页面', async () => {
  const harness = createHarness({
    respond(message) {
      if (message.type === 'RENDER_AND_EXPORT') return { success: true, ticket: TICKET }
    },
  })
  harness.chrome.runtime.id = undefined
  await harness.handlers.onDoExport(SETTINGS, 'computer_download')
  assert.deepEqual(harness.events.map(event => event.type), ['loading', 'error'])
  assert.equal(harness.events[1].message, '检测到插件刚刚更新，请按 F5 刷新网页后重试！')
  assert.equal(harness.sent.length, 0)
})

test('未捕获到有效题目时不发起排版请求', async () => {
  const harness = createHarness({
    paper: null,
    respond() {
      assert.fail('不应发起排版请求')
    },
  })
  await harness.handlers.onDoExport(SETTINGS, 'computer_download')
  assert.deepEqual(harness.events.map(event => event.type), ['loading', 'error'])
  assert.match(harness.events[1].message, /未能从当前页面捕获到有效题目/)
  assert.equal(harness.sent.length, 0)
})

test('快速打印入口使用默认排版设置并要求手机同步', async () => {
  const delivery = deliveryView()
  const harness = createHarness({
    respond(message) {
      if (message.type === 'RENDER_AND_EXPORT') return { success: true, ticket: TICKET }
      if (message.type === 'GET_RENDER_EXPORT') return { success: true, status: 'succeeded', delivery }
    },
  })
  await harness.handlers.onRequestQuickPrint()
  assert.equal(harness.sent[0].payload.target, 'mobile_sync')
  assert.equal(harness.sent[0].payload.settings, SETTINGS)
  assert.equal(harness.events.at(-1).type, 'delivery')
})

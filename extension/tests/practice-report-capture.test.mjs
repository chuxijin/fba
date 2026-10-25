import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'
import { compileSource, importTypeScript } from './helpers/typescript.mjs'

const report = await importTypeScript(new URL('../src/adapters/fenbi/report.ts', import.meta.url))
const { FenbiReportCache } = await importTypeScript(new URL('../src/adapters/fenbi/report-cache.ts', import.meta.url))
const contentCode = compileSource(await readFile(new URL('../src/content/index.ts', import.meta.url), 'utf8'))
const interceptorCode = compileSource(await readFile(new URL('../src/content/interceptor.ts', import.meta.url), 'utf8'))
const sessionCode = compileSource(await readFile(new URL('../src/adapters/fenbi/session.ts', import.meta.url), 'utf8'))
const href = 'https://spa.fenbi.com/ti/exam/solution/5_1_report?routecs=xingce'
const submittedAt = Date.parse('2026-10-19T10:00:00Z')
const solution = {
  exerciseId: '5_1_report', name: '行测模考',
  userAnswers: { q2: { status: 10, time: 0 }, q1: { status: 1, time: 30, answer: { choice: '0' } } },
}
const details = [{ name: '数量关系', questionCount: 2, correctCount: 1, time: 30,
  children: [{ name: '数学运算', questionCount: 2, correctCount: 1, time: 30 }] }]
const getReport = {
  exerciseId: '5_1_report', subReports: [
    { paperId: 1, fullmark: 100, score: 50, submitTime: submittedAt }, {}, {}, {}, {},
    { courseReports: [{ details }] },
  ],
}
const staticSolution = {
  card: { children: [{ name: '数量关系', children: [{ key: 'q1' }, { key: 'q2', materialKeys: ['m1'] }] }] },
  materials: [{ globalId: 'm1', content: '<p>材料</p>' }],
  solutions: ['q1', 'q2'].map(globalId => ({
    globalId, content: `<p>${globalId}</p>`, accessories: [{ options: ['甲', '乙'] }],
    correctAnswer: { choice: '0' }, solution: '<p>官方解析</p>', keypoints: [{ name: '数学运算' }],
  })),
}

function startPage(fetchResponse) {
  const location = { href, origin: 'https://spa.fenbi.com' }
  const window = new EventTarget()
  const messages = []
  const requests = []
  const drafts = []
  const statuses = []
  const backendMessages = []
  let handlers
  Object.assign(window, { location, postMessage(data) {
    messages.push(data)
    queueMicrotask(() => {
      const event = new Event('message')
      Object.assign(event, { source: window, origin: location.origin, data })
      window.dispatchEvent(event)
    })
  }, fetch: async url => {
    requests.push(url)
    if (fetchResponse) return fetchResponse
    throw new Error('报告读取不允许发起 fetch')
  } })
  class Xhr extends EventTarget {
    responseType = ''
    response = null
    get responseText() {
      if (this.responseType === 'json') throw new Error('responseText is unavailable for JSON responses')
      return JSON.stringify(this.response)
    }
    open(_method, url) { this.url = url }
    send() { requests.push(this.url) }
    reply(data, responseType = 'json') {
      this.responseType = responseType
      this.response = data
      this.dispatchEvent(new Event('load'))
    }
  }
  const document = new EventTarget()
  Object.assign(document, { readyState: 'interactive', querySelectorAll: () => [] })
  const context = vm.createContext({
    window, location, document, XMLHttpRequest: Xhr, URL, console,
    history: { pushState(_state, _title, url) { location.href = String(url) }, replaceState() {} },
    crypto: { randomUUID: () => '12345678-1234-1234-1234-123456789abc' },
    setTimeout: (fn, delay) => fn.name === 'finish' ? setTimeout(fn, delay) : 0,
    clearTimeout, setInterval() {}, exports: {},
    chrome: { runtime: { onMessage: { addListener() {} }, sendMessage: async message => {
      backendMessages.push(message)
      return { success: true, created: true }
    } } },
    require(name) {
      if (name === '../adapters/fenbi/report') return report
      if (name === '../adapters/fenbi/report-cache') return { FenbiReportCache }
      if (name === '../adapters') return { fenbiSession: {
        getPaper: () => null, handleNetworkPayload: () => null, reset() {},
      } }
      if (name === './ui/mount') return { mountReformatterApp(value) {
        handlers = value
        return { setReportDraft: draft => drafts.push(draft), setReportStatus: (status, message) => statuses.push({ status, message }), resetPaper() {} }
      } }
      throw new Error(`Unexpected import: ${name}`)
    },
  })
  vm.runInContext(interceptorCode, context)
  function receive(url, data, type = 'json') {
    const xhr = new Xhr()
    xhr.open('GET', url)
    xhr.send()
    xhr.reply(data, type)
    return xhr
  }
  return {
    location, window, requests, messages, drafts, statuses, backendMessages, receive,
    mount: () => vm.runInContext(contentCode, context),
    importReport: () => handlers.onImportReport(),
    saveReport: draft => handlers.onSaveReport(draft),
  }
}

test('report import replays pre-existing JSON XHR packets without making a network request', async () => {
  const page = startPage()
  page.receive('https://tiku.fenbi.com/combine/static/solution?key=signed', staticSolution)
  page.receive('https://tiku.fenbi.com/combine/exercise/getReport?key=5_1_report', { code: 1, data: getReport })
  page.receive('https://tiku.fenbi.com/combine/exercise/getSolution?key=5_1_report', { code: 1, data: solution })
  // 原始响应早于 content script 初始化，点击时必须从 MAIN 世界缓存恢复。
  await new Promise(resolve => setImmediate(resolve))
  page.mount()
  const before = page.requests.length
  await page.importReport()
  assert.equal(page.requests.length, before, '点击读取不得增加任何粉笔请求')
  assert.equal(page.backendMessages.length, 0, '读取预览不得提前提交后端')
  assert.equal(page.drafts.length, 1)
  const draft = page.drafts[0]
  assert.equal(draft.practiced_at, '2026-10-19')
  assert.equal(draft.score, 50)
  assert.equal(draft.questions.length, 2)
  assert.deepEqual(draft.questions.map(q => [q.source_question_key, q.position, q.status]), [
    ['q1', 1, 'correct'], ['q2', 2, 'unanswered'],
  ])
  assert.equal(draft.questions[1].materials[0].content, '<p>材料</p>')
  assert.deepEqual(draft.questions[0].module_path, ['数量关系', '数学运算'])
  await page.saveReport(draft)
  assert.equal(page.backendMessages.length, 1, '只有确认保存才提交一次后端')
  assert.equal(page.backendMessages[0].type, 'IMPORT_PRACTICE_REPORT')
  assert.equal(page.requests.length, before)
})

test('missing cached parsing content produces an explicit error and never fetches it', async () => {
  const page = startPage()
  page.mount()
  page.receive('https://tiku.fenbi.com/combine/exercise/getReport', getReport, 'text')
  page.receive('https://tiku.fenbi.com/combine/exercise/getSolution', solution)
  const before = page.requests.length
  await page.importReport()
  assert.equal(page.drafts.length, 0)
  assert.equal(page.statuses.at(-1).status, 'error')
  assert.match(page.statuses.at(-1).message, /尚未捕获本卷逐题解析/)
  assert.equal(page.requests.length, before)
})

test('fetch interception reads a cloned page response and replay never repeats that request', async () => {
  const response = { clone: () => ({ json: async () => ({ code: 1, data: solution }) }) }
  const page = startPage(response)
  const returned = await page.window.fetch('/combine/exercise/getSolution?key=5_1_report')
  assert.equal(returned, response, '拦截不修改页面收到的响应')
  await new Promise(resolve => setImmediate(resolve))
  page.window.postMessage({ source: 'GONGKAO_CONTENT_REQUEST_EXAM', requestId: 'replay-12345' })
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(page.requests.length, 1)
  assert.equal(page.messages.filter(message => message.type === 'RAW_API_INTERCEPTED').length, 2)
})

test('cached history is used by report key while a missing date stays unset', () => {
  const cache = new FenbiReportCache()
  cache.capture('/combine/exercise/getSolution', solution, href)
  assert.equal(cache.read(href).history.updatedTime, undefined)
  cache.capture('/combine/exercise/getExerciseBriefHistory', { code: 1, data: { historyItems: [
    { exerciseKey: 'other', updatedTime: 1, score: 99 },
    { exerciseKey: '5_1_report', updatedTime: submittedAt, score: 50, fullScore: 100 },
  ] } }, href)
  assert.equal(cache.read(href).history.updatedTime, submittedAt)
  assert.equal(cache.read(href).history.score, 50)
  assert.equal(cache.read(href.replace('5_1_report', '5_1_other')).solution, undefined)
})

test('a same-sized previous paper cannot satisfy the current report parsing cache', () => {
  const cache = new FenbiReportCache()
  cache.capture('/combine/static/solution?key=old', staticSolution, href)
  const otherHref = href.replace('5_1_report', '5_1_other')
  cache.capture('/combine/exercise/getSolution', {
    ...solution, exerciseId: '5_1_other', userAnswers: {
      q3: { status: 1, time: 10, answer: { choice: '0' } }, q4: { status: 10, time: 0 },
    },
  }, otherHref)
  assert.equal(cache.read(otherHref).staticSolution, undefined)
  assert.equal(cache.read(href).staticSolution, null)
})

test('XHR replay retains the page at request time rather than relabeling a late response', async () => {
  const page = startPage()
  const xhr = page.receive('/combine/exercise/getSolution', solution)
  page.location.href = href.replace('5_1_report', '5_1_other')
  xhr.reply(solution)
  page.window.postMessage({ source: 'GONGKAO_CONTENT_REQUEST_EXAM', requestId: 'replay-12345' })
  await new Promise(resolve => setImmediate(resolve))
  const replayed = page.messages.filter(message => message.type === 'RAW_API_INTERCEPTED')
  assert.ok(replayed.length)
  assert.ok(replayed.every(message => message.pageUrl === href))
})

test('static solution packets are retained as question content instead of being mistaken for answer sheets', () => {
  const exports = {}
  const aggregated = []
  vm.runInNewContext(sessionCode, { exports, window: {}, require(name) {
    if (name === '../types') return { DEFAULT_TYPOGRAPHY_SETTINGS: {} }
    if (name === './index') return { adaptFenbiPaper(data) {
      aggregated.push(data)
      return { total_questions: data.solutions.length, sections: [] }
    } }
    throw new Error(`Unexpected import: ${name}`)
  } })
  const session = exports.fenbiSession
  assert.equal(session.handleNetworkPayload('/combine/exercise/getSolution', solution), null)
  const paper = session.handleNetworkPayload('/combine/static/solution?key=signed', staticSolution)
  assert.equal(paper.total_questions, 2)
  assert.equal(session.getPaper(), paper)
  assert.equal(aggregated[0].userAnswersMap.get('q1'), '0')
  assert.equal(aggregated[0].solutions[1].solution, '<p>官方解析</p>')
})

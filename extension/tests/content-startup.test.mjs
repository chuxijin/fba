import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'
import { compileSource, importTypeScript } from './helpers/typescript.mjs'

const code = compileSource(await readFile(new URL('../src/content/index.ts', import.meta.url), 'utf8'))
const { FenbiReportCache } = await importTypeScript(new URL('../src/adapters/fenbi/report-cache.ts', import.meta.url))

function start(readyState) {
  const document = new EventTarget()
  Object.assign(document, { readyState, head: null, documentElement: null })
  const window = new EventTarget()
  const received = []
  const mounted = []
  const papers = []
  const paper = { title: '启动时捕获的报告', total_questions: 10 }
  let cached = null
  const adapters = { fenbiSession: {
    getPaper: () => cached,
    handleNetworkPayload: () => { cached = paper; return paper },
  } }
  const modules = {
    '../adapters': adapters,
    '../adapters/fenbi/report': { fenbiReportRoute: () => null },
    '../adapters/fenbi/report-cache': { FenbiReportCache },
    './ui/mount': { mountReformatterApp: handlers => {
      mounted.push(handlers)
      return { setPaper: value => papers.push(value) }
    } },
  }
  vm.runInNewContext(code, {
    exports: {}, require: name => modules[name], document, window,
    location: { href: 'https://spa.fenbi.com/ti/exam/solution/1_2_report', origin: 'https://spa.fenbi.com' },
    chrome: { runtime: { onMessage: { addListener: fn => received.push(fn) } } },
    setTimeout() {}, setInterval() {}, console,
  })
  return { document, window, received, mounted, papers, paper }
}

test('document_start without a document root still registers messages and mounts on DOMContentLoaded', () => {
  const runtime = start('loading')
  assert.equal(runtime.received.length, 1, '早期启动不能中断 Popup 消息监听注册')
  assert.equal(runtime.mounted.length, 0)
  const event = new Event('message')
  Object.assign(event, { source: runtime.window, origin: 'https://spa.fenbi.com', data: {
    source: 'GONGKAO_REFORMATTER_INTERCEPTOR', type: 'RAW_API_INTERCEPTED',
    url: 'https://spa.fenbi.com/combine/exercise/getsolution', data: { questions: [] },
  } })
  runtime.window.dispatchEvent(event)
  runtime.document.dispatchEvent(new Event('DOMContentLoaded'))
  assert.equal(runtime.mounted.length, 1)
  assert.equal(runtime.papers.at(-1), runtime.paper, 'DOM 就绪前捕获的数据必须同步给悬浮卡片')
  runtime.document.dispatchEvent(new Event('DOMContentLoaded'))
  assert.equal(runtime.mounted.length, 1)
  let response
  runtime.received[0]({ type: 'CHECK_STATUS' }, {}, value => { response = value })
  assert.equal(response.hasContent, true)
  assert.equal(response.questionCount, 10)
})

test('an already interactive page mounts its floating card immediately without waiting for load', () => {
  const runtime = start('interactive')
  assert.equal(runtime.mounted.length, 1)
  assert.equal(runtime.received.length, 1)
})

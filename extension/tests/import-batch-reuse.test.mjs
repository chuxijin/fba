import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import vm from 'node:vm'
import * as vue from 'vue'
import { compileSource, importTypeScript } from './helpers/typescript.mjs'

const listeners = []
const storage = { fba_auth_token: { access_token: 'local-test-token', access_token_expire_time: '2099-01-01T00:00:00Z' } }
const progress = []
globalThis.chrome = {
  runtime: { onMessage: { addListener(fn) { listeners.push(fn) } }, getURL: path => `chrome-extension://test/${path}` },
  storage: {
    local: {
      async get(keys) { return Object.fromEntries(keys.filter(key => key in storage).map(key => [key, storage[key]])) },
      async set(values) { Object.assign(storage, values) },
      async remove(keys) { for (const key of keys) delete storage[key] },
    },
    onChanged: { addListener() {} },
  },
  tabs: { async query() { return [] }, async sendMessage(_tab, message) { progress.push(message.payload) } },
}
await importTypeScript(new URL('../src/background/index.ts', import.meta.url))
const send = message => new Promise(resolve => listeners[0](message, { tab: { id: 1 }, frameId: 0 }, resolve))
const json = data => new Response(JSON.stringify({ code: 200, data }))

test('29道分片导入：18新增+11已有均成功，所有分片共用批次', async () => {
  const requests = []
  progress.length = 0
  globalThis.fetch = async (url, init) => {
    assert.match(url, /wrong-questions\/external$/)
    const items = JSON.parse(init.body)
    requests.push(init.headers['X-Import-Batch-Id'])
    const reused = requests.length === 1 ? 11 : 0
    return json({ succeeded: items.length, created: items.length - reused, reused, failed: 0, items, failures: [] })
  }
  const result = await send({ type: 'IMPORT_WRONG_QUESTIONS', payload: { items: Array.from({ length: 29 }, (_, index) => ({ external_key: `q${index}` })) } })
  assert.equal(result.success, true)
  assert.equal(result.imported, 29)
  assert.equal(result.created, 18)
  assert.equal(result.reused, 11)
  assert.equal(result.failed, 0)
  assert.equal(result.importedKeys.length, 29)
  assert.equal(new Set(requests).size, 1)
  assert.equal(progress.at(-1).reused, 11)
})

test('全是已有题也返回成功关联的批次，不归类为失败或跳过', async () => {
  globalThis.fetch = async (_url, init) => {
    const items = JSON.parse(init.body)
    return json({ succeeded: items.length, created: 0, reused: items.length, failed: 0, items })
  }
  const result = await send({ type: 'IMPORT_WRONG_QUESTIONS', payload: { items: [{ external_key: 'existing' }] } })
  assert.equal(result.imported, 1)
  assert.equal(result.reused, 1)
  assert.equal(result.allDuplicates, false)
  assert.ok(result.importBatchId)
})

test('旧后端缺少分类时不虚报新增数，真正失败仍保留', async () => {
  globalThis.fetch = async () => json({ succeeded: 1, failed: 1, items: [{ external_key: 'ok' }], failures: [{ external_key: 'bad', reason: '答案错误' }] })
  const result = await send({ type: 'IMPORT_WRONG_QUESTIONS', payload: { items: [{ external_key: 'ok' }, { external_key: 'bad' }] } })
  assert.equal(result.imported, 1)
  assert.equal(result.failed, 1)
  assert.equal(result.created, undefined)
  assert.match(result.error, /答案错误/)
})

test('撤销结果透传只解除关联的题量', async () => {
  globalThis.fetch = async (_url, init) => {
    assert.equal(init.method, 'DELETE')
    return json({ deleted_states: 18, deleted_questions: 18, detached_states: 11 })
  }
  const result = await send({ type: 'UNDO_IMPORT_BATCH', payload: { importBatchId: 'new-batch' } })
  assert.equal(result.deletedStates, 18)
  assert.equal(result.detachedStates, 11)
})

const { IDLE_IMPORT_STATE } = await importTypeScript(new URL('../src/adapters/importer.ts', import.meta.url))
const content = await readFile(new URL('../src/content/index.ts', import.meta.url), 'utf8')
const start = content.indexOf('  async function handleImportWrongQuestions()')
const end = content.indexOf('  async function handleUndoImportBatch()', start)
function contentHarness(keys = [], legacy = false) {
  const items = Array.from({ length: 29 }, (_, index) => ({ external_key: `q${index}` }))
  const sent = []
  const states = []
  const context = {
    currentUnifiedPaper: { title: '第一季', total_questions: 120 },
    importedWrongKeys: new Set(keys), lastImportBatchId: '', lastImportBatchComplete: false, IDLE_IMPORT_STATE,
    uiApp: { setImportState(state) { states.push(state) } },
    backfillPaperAnswers: async paper => paper,
    attachFenbiWrongOccurrences: result => result,
    location: { href: 'https://spa.fenbi.com/ti/exam/solution/1_1_test' },
    reportCache: { read() { return {} } },
    buildWrongImportItems: () => ({ items, skipped: [] }),
    chrome: { runtime: { id: 'test', sendMessage(message, callback) {
      sent.push(message)
      callback({ success: true, imported: 29, ...(legacy ? {} : { created: 18, reused: 11 }), failed: 0, importedKeys: items.map(item => item.external_key), importBatchId: 'new-batch' })
    } } },
  }
  vm.createContext(context)
  vm.runInContext(compileSource(content.slice(start, end)), context)
  return { run: () => context.handleImportWrongQuestions(), sent, states }
}

test('网页不能过滤已导入的11道：本次仍发送完整29道以关联整卷', async () => {
  const harness = contentHarness(Array.from({ length: 11 }, (_, index) => `q${index}`))
  await harness.run()
  assert.equal(harness.sent[0].payload.items.length, 29)
  assert.equal(harness.states.at(-1).imported, 29)
  assert.equal(harness.states.at(-1).created, 18)
  assert.equal(harness.states.at(-1).reused, 11)
  assert.equal(harness.states.at(-1).skipped, 0)
  await harness.run()
  assert.equal(harness.sent.length, 1)
  assert.equal(harness.states.at(-1).batchId, 'new-batch')
})

test('网页连接旧后端时不能把缓存误报为完整的新批次', async () => {
  const harness = contentHarness([], true)
  await harness.run()
  await harness.run()
  assert.equal(harness.sent.length, 2)
  assert.equal(harness.states.at(-1).created, undefined)
  assert.equal(harness.states.at(-1).reused, undefined)
})

test('悬浮窗同时展示总成功数、新增数、已有数及失败原因', async () => {
  const require = createRequire(import.meta.url)
  const requireFromVue = createRequire(require.resolve('vue'))
  const { parse, compileScript } = requireFromVue('@vue/compiler-sfc')
  const source = await readFile(new URL('../src/content/ui/FloatingWidget.vue', import.meta.url), 'utf8')
  const compiled = compileScript(parse(source).descriptor, { id: 'import-count-test' })
  const exports = {}
  vm.runInNewContext(compileSource(compiled.content), {
    exports, require: name => name === 'vue' ? vue : { IDLE_IMPORT_STATE },
    chrome: { runtime: { getURL: () => '', getManifest: () => ({ version: 'test' }) } },
  })
  const props = vue.reactive({ questionCount: 120, importState: { status: 'done', imported: 29, created: 18, reused: 11, failed: 0, skipped: 0, batchId: 'new-batch' } })
  const state = exports.default.setup(props, { expose() {}, emit() {} })
  assert.match(state.importButtonText.value, /29/)
  assert.match(state.importHint.value, /新增 18 道，已有 11 道/)
  props.importState.message = '真实失败原因'
  assert.match(state.importHint.value, /真实失败原因/)
})

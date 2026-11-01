import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import vm from 'node:vm'
import * as realVue from 'vue'
import { compileSource } from './helpers/typescript.mjs'

const requireFromTests = createRequire(import.meta.url)
const requireFromVue = createRequire(requireFromTests.resolve('vue'))
const { parse, compileScript } = requireFromVue('@vue/compiler-sfc')

const sfcSource = await readFile(new URL('../src/content/ui/App.vue', import.meta.url), 'utf8')
const { descriptor, errors } = parse(sfcSource, { filename: 'App.vue' })
if (errors.length) throw errors[0]
const compiled = compileScript(descriptor, { id: 'app-feedback-test' })

function createHarness(exportMessage) {
  const calls = []
  const adapters = {
    countWrongQuestions: () => 0,
    parseMistakePageMeta: () => null,
    IDLE_IMPORT_STATE: {},
    UnifiedPaper: undefined,
    RenderTypographySettings: undefined,
    MistakePageMeta: undefined,
    ImportState: undefined,
    DEFAULT_TYPOGRAPHY_SETTINGS: { fontFamily: '', fontSize: 12 },
  }
  const modules = {
    vue: realVue,
    './FloatingWidget.vue': {},
    './SettingsModal.vue': {},
    './PracticeReportImport.vue': {},
    '../../adapters/fenbi/report': { fenbiReportRoute: () => null },
    '../../utils/export-flow': {
      exportMessage: async (type, payload) => {
        calls.push({ type, payload: payload === undefined ? undefined : JSON.parse(JSON.stringify(payload)) })
        return exportMessage(type, payload)
      },
    },
    '../../adapters': adapters,
  }

  const exports = {}
  vm.runInNewContext(compileSource(compiled.content), {
    exports,
    require(name) {
      if (!(name in modules)) throw new Error(`Unexpected import: ${name}`)
      return modules[name]
    },
    chrome: { runtime: { getURL: () => 'chrome-extension://test/icons/icon48.png', getManifest: () => ({ version: '1.0.3' }) } },
    location: { href: 'https://spa.fenbi.com/ti/exam/solution/1_2_report' },
    console,
  })

  const component = exports.default
  const exposed = {}
  const emissions = []
  const state = component.setup({}, {
    expose: methods => Object.assign(exposed, methods),
    emit: (...args) => emissions.push(args),
  })
  return { state, exposed, emissions, calls }
}

test('悬浮窗建议反馈通过固定 OPEN_SUPPORT 消息打开插件内反馈页', async () => {
  const harness = createHarness(async () => ({ success: true }))
  await harness.state.handleFeedback()
  assert.deepEqual(harness.calls, [{ type: 'OPEN_SUPPORT', payload: { section: 'feedback' } }])
  assert.equal(harness.state.feedbackError.value, '')
})

test('反馈页打开失败时在悬浮窗内提示可重试，不伪造成功', async () => {
  const harness = createHarness(async () => { throw new Error('插件通信失败') })
  await harness.state.handleFeedback()
  assert.equal(harness.state.feedbackError.value, '插件通信失败')

  const retry = createHarness(async () => { throw new Error('Extension context invalidated') })
  await retry.state.handleFeedback()
  assert.equal(retry.state.feedbackError.value, 'Extension context invalidated')
})

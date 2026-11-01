import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'
import { compileSource } from './helpers/typescript.mjs'

const mountCode = compileSource(await readFile(new URL('../src/content/ui/mount.ts', import.meta.url), 'utf8'))

function createMountHarness() {
  const calls = []
  const app = {
    setPaper: value => calls.push(['setPaper', value]),
    setPaperInfo: (title, count) => calls.push(['setPaperInfo', title, count]),
    setImportState: value => calls.push(['setImportState', value]),
    setReportDraft: value => calls.push(['setReportDraft', value]),
    setReportStatus: (status, message) => calls.push(['setReportStatus', status, message]),
    resetPaper: () => calls.push(['resetPaper']),
    openModal: () => calls.push(['openModal']),
    closeModal: () => calls.push(['closeModal']),
    showLoading: target => calls.push(['showLoading', target]),
    showDelivery: options => calls.push(['showDelivery', options]),
    showError: message => calls.push(['showError', message]),
  }
  const appended = []
  let component = null
  let props = null
  const shadowRoot = { appendChild: node => appended.push(node) }
  const document = {
    getElementById: () => null,
    createElement: () => ({ style: {}, id: '', attachShadow: () => shadowRoot, appendChild() {} }),
    body: { appendChild() {} },
  }
  const modules = {
    vue: {
      createApp(value, values) {
        component = value
        props = values
        return { mount: () => app }
      },
    },
    './App.vue': { default: 'AppComponent' },
    './style.css?inline': { default: '/* styles */' },
    './practice-report.css?inline': { default: '/* report */' },
  }
  const exports = {}
  vm.runInNewContext(mountCode, {
    exports,
    require(name) {
      if (!(name in modules)) throw new Error(`Unexpected import: ${name}`)
      return modules[name]
    },
    document,
  })
  return {
    mount: handlers => exports.mountReformatterApp(handlers),
    calls,
    appended,
    get component() { return component },
    get props() { return props },
  }
}

const handlers = {
  onRequestReformat() {},
  onRequestQuickPrint() {},
  onDoExport() {},
  onImportWrong() {},
  onUndoImport() {},
  onImportReport() {},
  onSaveReport() {},
}

test('UI 挂载后 showDelivery 原样透传交付视图', () => {
  const harness = createMountHarness()
  const instance = harness.mount(handlers)
  const delivery = {
    files: [
      { downloadUrl: 'http://127.0.0.1:8000/api/v1/render-books/public/download/vol1', fileName: '卷1.pdf' },
      { downloadUrl: 'http://127.0.0.1:8000/api/v1/render-books/public/download/vol2', fileName: '卷2.pdf' },
    ],
    qrCodeUrl: 'http://127.0.0.1:8000/api/v1/render-books/public/minicode/qr1',
    savedPath: 'C:/dl/卷1.pdf',
    remainingQuota: 2,
    failedFiles: [],
    downloadWarning: '',
    downloadStarted: true,
  }
  instance.showDelivery(delivery)
  instance.showLoading('computer_download')
  instance.showError('排版失败，请重试')
  instance.setPaper({ title: '卷' })

  assert.deepEqual(harness.calls, [
    ['showDelivery', delivery],
    ['showLoading', 'computer_download'],
    ['showError', '排版失败，请重试'],
    ['setPaper', { title: '卷' }],
  ])
})

test('UI 挂载把导出事件处理器原样传给 App 并注入样式容器', () => {
  const harness = createMountHarness()
  harness.mount(handlers)

  assert.equal(harness.component, 'AppComponent')
  assert.equal(harness.props.onDoExport, handlers.onDoExport)
  assert.equal(harness.props.onRequestQuickPrint, handlers.onRequestQuickPrint)
  assert.ok(harness.appended.length >= 2, '样式与 Vue 容器都应挂到 shadow root')
})

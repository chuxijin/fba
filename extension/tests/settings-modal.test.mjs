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

const sfcSource = await readFile(new URL('../src/content/ui/SettingsModal.vue', import.meta.url), 'utf8')
const { descriptor, errors } = parse(sfcSource, { filename: 'SettingsModal.vue' })
if (errors.length) throw errors[0]
const compiled = compileScript(descriptor, { id: 'settings-modal-test' })

const vueLike = {
  ...realVue,
  onMounted() {},
  onUnmounted() {},
}

function deferred() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

const flush = () => new Promise(resolve => setImmediate(resolve))

function createHarness({ qr, download } = {}) {
  const messages = []
  const qrRequests = []
  const downloadRequests = []
  const subscriptions = []
  let qrHandler = qr || (async payload => ({ image: `data:image/png;base64,${Buffer.from(payload.url).toString('base64')}` }))
  let downloadHandler = download || (async () => ({
    failedFiles: [], downloadWarning: '', downloadStarted: true, savedPath: 'C:/dl/卷1.pdf',
  }))

  const exportMessage = async (type, payload) => {
    messages.push({ type, payload })
    if (type === 'GET_RENDER_QR') {
      qrRequests.push(payload)
      return qrHandler(payload, qrRequests.length - 1)
    }
    throw new Error(`SettingsModal 不应发送 ${type}`)
  }

  const requestFileDownloads = async (files) => {
    downloadRequests.push(files)
    return downloadHandler(files)
  }

  const accountStore = {
    subscribe(fn) { subscriptions.push(fn); return () => {} },
    refresh() {},
  }

  const adapters = {
    DEFAULT_TYPOGRAPHY_SETTINGS: { fontFamily: '', fontSize: 12 },
    RenderTypographySettings: undefined,
    UnifiedPaper: undefined,
    MistakePageMeta: undefined,
  }

  const modules = {
    vue: vueLike,
    '../../adapters': adapters,
    '../../utils/account-state': { accountStore, AccountState: undefined },
    '../../utils/export-flow': { exportMessage, requestFileDownloads },
  }

  const exports = {}
  vm.runInNewContext(compileSource(compiled.content), {
    exports,
    require(name) {
      if (!(name in modules)) throw new Error(`Unexpected import: ${name}`)
      return modules[name]
    },
    chrome: { runtime: { getURL: () => 'chrome-extension://test/icons/icon48.png' } },
    setInterval: () => 1,
    clearInterval() {},
    console,
  })

  const component = exports.default
  const props = {
    modelValue: false,
    paper: { title: '模考卷', total_questions: 2, sections: [], metadata: {} },
    mistakeMeta: null,
  }
  const exposed = {}
  const emissions = []
  const state = component.setup(props, {
    expose: methods => Object.assign(exposed, methods),
    emit: (...args) => emissions.push(args),
  })

  return {
    state,
    exposed,
    emissions,
    props,
    subscriptions,
    messages,
    qrRequests,
    downloadRequests,
    setQr(handler) { qrHandler = handler },
    setDownload(handler) { downloadHandler = handler },
  }
}

const QR_A = 'http://127.0.0.1:8000/api/v1/render-books/public/minicode/qrA'
const QR_B = 'http://127.0.0.1:8000/api/v1/render-books/public/minicode/qrB'

test('showLoading 清空上一次交付的二维码与下载状态', async () => {
  const harness = createHarness()
  harness.exposed.showDelivery({
    qrCodeUrl: QR_A,
    savedPath: 'C:/dl/旧卷.pdf',
    failedFiles: [{ downloadUrl: '/api/v1/render-books/public/download/old', fileName: '旧卷.pdf' }],
    downloadWarning: '旧卷.pdf：DENIED',
    downloadStarted: true,
  })
  await flush()
  assert.equal(harness.state.qrImage.value, `data:image/png;base64,${Buffer.from(QR_A).toString('base64')}`)
  const version = harness.state.deliveryVersion

  harness.exposed.showLoading('mobile_sync')

  assert.equal(harness.state.viewMode.value, 'loading')
  assert.equal(harness.state.qrCodeUrl.value, '')
  assert.equal(harness.state.qrImage.value, '')
  assert.equal(harness.state.qrError.value, '')
  assert.equal(harness.state.failedFiles.value.length, 0)
  assert.equal(harness.state.downloadWarning.value, '')
  assert.equal(harness.state.downloadStarted.value, false)
  assert.equal(harness.state.retryingDownload.value, false)
  assert.equal(harness.state.deliveryVersion, version + 1)
})

test('showDelivery 只独立请求二维码，不触发下载也不发送排版请求', async () => {
  const qr = deferred()
  const harness = createHarness({ qr: () => qr.promise })
  harness.exposed.showDelivery({
    qrCodeUrl: QR_A,
    savedPath: 'C:/dl/卷1.pdf',
    failedFiles: [],
    downloadWarning: '',
    downloadStarted: true,
  })

  assert.deepEqual(harness.qrRequests.map(request => request.url), [QR_A])
  assert.equal(harness.downloadRequests.length, 0)
  assert.deepEqual(harness.messages.map(message => message.type), ['GET_RENDER_QR'])

  qr.resolve({ image: 'data:image/png;base64,QR' })
  await flush()
  assert.equal(harness.state.qrImage.value, 'data:image/png;base64,QR')
  assert.equal(harness.state.savedPath.value, 'C:/dl/卷1.pdf')
  assert.equal(harness.state.downloadStarted.value, true)
})

test('二维码失败只记录错误，不改变已完成的下载结果', async () => {
  const harness = createHarness({ qr: async () => { throw new Error('小程序码生成失败') } })
  harness.exposed.showDelivery({
    qrCodeUrl: QR_A,
    savedPath: 'C:/dl/卷1.pdf',
    failedFiles: [],
    downloadWarning: '',
    downloadStarted: true,
  })
  await flush()

  assert.equal(harness.state.viewMode.value, 'delivery')
  assert.equal(harness.state.qrError.value, '小程序码生成失败')
  assert.equal(harness.state.qrImage.value, '')
  assert.equal(harness.state.savedPath.value, 'C:/dl/卷1.pdf')
  assert.equal(harness.state.downloadStarted.value, true)
  assert.equal(harness.state.downloadWarning.value, '')
  assert.equal(harness.state.failedFiles.value.length, 0)
  assert.equal(harness.downloadRequests.length, 0)
  assert.equal(harness.state.retryingDownload.value, false)
})

test('重新加载二维码会再次独立请求并清除旧错误', async () => {
  let calls = 0
  const harness = createHarness({
    qr: async () => {
      calls++
      if (calls === 1) throw new Error('小程序码生成失败')
      return { image: 'data:image/png;base64,RETRY' }
    },
  })
  harness.exposed.showDelivery({ qrCodeUrl: QR_A, downloadStarted: true, failedFiles: [] })
  await flush()
  assert.equal(harness.state.qrError.value, '小程序码生成失败')

  await harness.state.loadQrCode()
  await flush()

  assert.equal(calls, 2)
  assert.equal(harness.qrRequests.length, 2)
  assert.equal(harness.state.qrError.value, '')
  assert.equal(harness.state.qrImage.value, 'data:image/png;base64,RETRY')
  assert.equal(harness.state.qrLoading.value, false)
  assert.equal(harness.state.downloadStarted.value, true)
  assert.deepEqual(harness.downloadRequests, [])
})

test('retryDownload 只把 failedFiles 交给下载接口，不重新发送排版请求', async () => {
  const failed = [{ downloadUrl: '/api/v1/render-books/public/download/vol2', fileName: '卷2.pdf' }]
  const harness = createHarness({
    download: async () => ({
      failedFiles: [], downloadWarning: '', downloadStarted: true, savedPath: 'C:/dl/卷2.pdf',
    }),
  })
  harness.exposed.showDelivery({
    qrCodeUrl: '',
    savedPath: '',
    failedFiles: failed,
    downloadWarning: '卷2.pdf：DENIED',
    downloadStarted: false,
  })
  assert.equal(harness.messages.length, 0)

  await harness.state.retryDownload()

  assert.deepEqual(harness.downloadRequests, [failed])
  assert.equal(harness.messages.some(message => message.type === 'RENDER_AND_EXPORT'), false)
  assert.equal(harness.messages.length, 0)
  assert.deepEqual(harness.state.failedFiles.value, [])
  assert.equal(harness.state.downloadWarning.value, '')
  assert.equal(harness.state.downloadStarted.value, true)
  assert.equal(harness.state.savedPath.value, 'C:/dl/卷2.pdf')
  assert.equal(harness.state.retryingDownload.value, false)
})

test('迟到的旧二维码不会覆盖新交付的二维码', async () => {
  const first = deferred()
  const second = deferred()
  const harness = createHarness({
    qr: (payload) => payload.url === QR_A ? first.promise : second.promise,
  })

  harness.exposed.showDelivery({ qrCodeUrl: QR_A, downloadStarted: true, failedFiles: [] })
  await flush()
  assert.equal(harness.qrRequests.length, 1)

  harness.exposed.showLoading('computer_download')
  harness.exposed.showDelivery({ qrCodeUrl: QR_B, downloadStarted: true, failedFiles: [] })
  await flush()
  assert.equal(harness.qrRequests.length, 2)

  first.resolve({ image: 'data:image/png;base64,STALE' })
  await flush()
  assert.equal(harness.state.qrImage.value, '')
  assert.notEqual(harness.state.qrImage.value, 'data:image/png;base64,STALE')

  second.resolve({ image: 'data:image/png;base64,NEW' })
  await flush()
  assert.equal(harness.state.qrImage.value, 'data:image/png;base64,NEW')
  assert.equal(harness.state.qrCodeUrl.value, QR_B)
  assert.equal(harness.state.downloadStarted.value, true)
  assert.equal(harness.downloadRequests.length, 0)
})

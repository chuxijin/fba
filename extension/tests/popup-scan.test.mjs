import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'
import { compileSource } from './helpers/typescript.mjs'

const source = await readFile(new URL('../src/popup/popup.ts', import.meta.url), 'utf8')
const code = compileSource(source)
const tick = () => new Promise(resolve => setImmediate(resolve))
async function flush(times = 6) { for (let index = 0; index < times; index++) await tick() }

function createElement() {
  const listeners = {}
  const classes = new Set()
  const element = {
    textContent: '',
    value: '',
    type: 'text',
    disabled: false,
    title: '',
    src: '',
    focused: false,
    style: {},
    dataset: {},
    attributes: {},
    children: [],
    classList: {
      add(name) { classes.add(name) },
      remove(name) { classes.delete(name) },
      contains(name) { return classes.has(name) },
    },
    addEventListener(type, fn) { (listeners[type] ||= []).push(fn) },
    dispatch(type, event = {}) {
      const target = { preventDefault() {}, target: element, key: '', ...event }
      return Promise.all((listeners[type] || []).map(fn => fn.call(element, target)))
    },
    focus() { element.focused = true },
    setAttribute(name, value) { element.attributes[name] = value },
    remove() {},
  }
  return element
}

function createHarness({ fetchScanQrcode, accountState, fetchCaptcha, pollScanStatus, loginWithPassword } = {}) {
  const elements = new Map()
  const documentListeners = {}
  const captchaCalls = []
  const pollCalls = []
  const loginCalls = []
  const saves = []
  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, createElement())
      return elements.get(id)
    },
    querySelectorAll() { return [] },
    addEventListener(type, fn) { (documentListeners[type] ||= []).push(fn) },
  }
  const window = new EventTarget()
  const storageListeners = []
  const chrome = {
    runtime: {
      getURL: path => `chrome-extension://test/${path}`,
      getManifest: () => ({ version: '1.0.3' }),
      sendMessage() {},
      onMessage: { addListener() {} },
    },
    storage: { onChanged: { addListener(fn) { storageListeners.push(fn) } } },
    tabs: {
      async query() { return [{ id: 1, active: true }] },
      sendMessage(_id, _message, callback) { callback?.({ hasContent: false }) },
      create() {},
    },
  }
  const timers = []
  const clock = { offset: 0 }
  const RealDate = Date
  function SandboxDate(...args) {
    return args.length ? new RealDate(...args) : new RealDate(RealDate.now() + clock.offset)
  }
  SandboxDate.now = () => RealDate.now() + clock.offset
  SandboxDate.parse = RealDate.parse
  SandboxDate.UTC = RealDate.UTC
  SandboxDate.prototype = RealDate.prototype
  const accountStore = {
    subscribe(fn) {
      fn(accountState || { status: 'ready', quota: {
        is_logged_in: false, remaining_quota: 3, daily_limit: 5, used_count: 2,
      } })
      return () => {}
    },
    async refresh() {},
  }
  const auth = {
    saveAuthSession: async (...args) => { saves.push(args) },
    logoutAuthSession: async () => {},
    fetchScanQrcode,
    pollScanStatus: async (...args) => {
      pollCalls.push(args[0])
      if (pollScanStatus) return pollScanStatus(...args)
      return { status: 'PENDING' }
    },
    fetchCaptcha: async (...args) => {
      captchaCalls.push(args[0])
      if (fetchCaptcha) return fetchCaptcha(...args)
      return { is_enabled: false, uuid: 'uuid', image: '' }
    },
    loginWithPassword: async (...args) => {
      loginCalls.push(args[0])
      if (loginWithPassword) return loginWithPassword(...args)
      throw new Error('不应使用账号密码登录')
    },
    sendAuthMessage: async () => { throw new Error('不应发送后台消息') },
  }
  const exports = {}
  vm.runInNewContext(code, {
    exports,
    require(name) {
      if (name === '../utils/auth') return auth
      if (name === '../utils/account-state') return { accountStore, AccountState: undefined }
      if (name === '../utils/auth-protocol') {
        return { BACKEND_BASE: 'https://api.yzxj.vip', IS_PRODUCTION: true }
      }
      throw new Error(`Unexpected import: ${name}`)
    },
    chrome,
    document,
    window,
    navigator: {},
    location: { href: 'chrome-extension://test/popup.html' },
    console,
    crypto,
    Date: SandboxDate,
    queueMicrotask,
    alert() {},
    setTimeout(fn, ms) { timers.push({ fn, ms }); return timers.length },
    clearTimeout() {},
    setInterval() { return 1 },
    clearInterval() {},
  })
  return {
    document,
    elements,
    element: id => document.getElementById(id),
    documentListeners,
    timers,
    clock,
    captchaCalls,
    pollCalls,
    loginCalls,
    saves,
    async open() {
      assert.equal(documentListeners.DOMContentLoaded?.length, 1)
      await documentListeners.DOMContentLoaded[0]()
    },
  }
}

function deferred() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

test('弹窗初始化版本、隐藏生产环境诊断且未登录额度来自服务端', async () => {
  const harness = createHarness({ fetchScanQrcode: async () => { throw new Error('不应拉二维码') } })
  await harness.open()
  assert.equal(harness.element('extension-version').textContent, 'v 1.0.3')
  assert.equal(harness.element('auth-diagnostics').style.display, 'none')
  assert.equal(harness.element('guest-quota-sub').textContent, '今日剩余 3 次试用')
  assert.equal(harness.element('hero-empty-title-text').textContent, '未检测到做题内容')
  assert.equal(harness.element('scan-qr-img').src, '')
})

test('扫码失败显示真实错误与重试入口，重试后展示新二维码', async () => {
  const requests = []
  const codes = [deferred(), deferred()]
  const harness = createHarness({
    fetchScanQrcode: async base => {
      requests.push(base)
      return codes[requests.length - 1].promise
    },
  })
  await harness.open()

  await harness.element('btn-show-scan').dispatch('click')
  await flush(2)
  assert.equal(requests.length, 1)
  assert.equal(requests[0], 'https://api.yzxj.vip')
  assert.equal(harness.element('view-scan').style.display, 'flex')
  assert.equal(harness.element('scan-qr-loading').textContent, '小程序码生成中…')
  assert.equal(harness.element('btn-scan-retry').disabled, true)

  codes[0].reject(new Error('登录二维码无效，请重试或使用账号密码登录'))
  await flush()
  assert.match(harness.element('scan-qr-loading').textContent, /^生成失败：登录二维码无效/)
  assert.match(harness.element('scan-main-hint').textContent, /重新获取二维码/)
  assert.equal(harness.element('scan-qr-img').style.display, 'none')
  assert.equal(harness.element('btn-scan-retry').disabled, false)

  await harness.element('btn-scan-retry').dispatch('click')
  await flush(2)
  assert.equal(requests.length, 2)
  assert.equal(harness.element('btn-scan-retry').disabled, true)
  codes[1].resolve({ scene_id: 'fba_0123456789abcdef', qrcode_data_url: 'data:image/png;base64,QR', expires_in: 120 })
  await flush()
  assert.equal(harness.element('scan-qr-img').src, 'data:image/png;base64,QR')
  assert.equal(harness.element('scan-qr-img').style.display, 'block')
  assert.equal(harness.element('scan-qr-loading').style.display, 'none')
  assert.equal(harness.element('btn-scan-retry').disabled, false)
  assert.equal(harness.element('scan-main-hint').textContent, '请使用微信扫描上方小程序码')
  assert.deepEqual(harness.timers.slice(-1).map(timer => timer.ms), [2000])
})

test('返回主视图会清理扫码状态，不残留旧二维码轮询', async () => {
  const harness = createHarness({
    fetchScanQrcode: async () => ({ scene_id: 'fba_0123456789abcdef', qrcode_data_url: 'data:image/png;base64,QR', expires_in: 120 }),
  })
  await harness.open()
  await harness.element('btn-show-scan').dispatch('click')
  await flush()
  assert.equal(harness.element('view-scan').style.display, 'flex')

  await harness.element('btn-back').dispatch('click')
  assert.equal(harness.element('view-main').style.display, 'flex')
  assert.equal(harness.element('view-scan').style.display, 'none')
  assert.equal(harness.element('auth-diagnostics').style.display, 'none')
})

test('验证码获取失败禁用提交，点击验证码区域可重试', async () => {
  let captchaCalls = 0
  const harness = createHarness({
    fetchCaptcha: async () => {
      captchaCalls++
      if (captchaCalls === 1) throw new Error('验证码服务超时')
      return { is_enabled: true, uuid: 'captcha-2', image: 'data:image/png;base64,CAPTCHA2' }
    },
  })
  await harness.open()
  await harness.element('tab-pwd').dispatch('click')
  await flush()

  assert.equal(captchaCalls, 1)
  assert.equal(harness.element('btn-pwd-login').disabled, true)
  assert.equal(harness.element('pwd-captcha-group').style.display, 'flex')
  assert.match(harness.element('pwd-error-msg').textContent, /验证码服务不可用：验证码服务超时。点击验证码区域重新加载。/)
  assert.equal(harness.element('captcha-loading').style.display, 'none')

  await harness.element('captcha-img-wrap').dispatch('click')
  await flush()

  assert.equal(captchaCalls, 2)
  assert.equal(harness.element('btn-pwd-login').disabled, false)
  assert.equal(harness.element('pwd-captcha-img').src, 'data:image/png;base64,CAPTCHA2')
  assert.equal(harness.element('pwd-captcha-img').style.display, 'block')
})

test('迟到的旧验证码响应不会覆盖新版本', async () => {
  const first = deferred()
  const second = deferred()
  const harness = createHarness({
    fetchCaptcha: () => (harness.captchaCalls.length === 1 ? first.promise : second.promise),
  })
  await harness.open()
  await harness.element('tab-pwd').dispatch('click')
  await flush()
  await harness.element('captcha-img-wrap').dispatch('click')
  await flush()
  assert.equal(harness.captchaCalls.length, 2)

  second.resolve({ is_enabled: true, uuid: 'new', image: 'data:image/png;base64,NEWCAPTCHA' })
  await flush()
  assert.equal(harness.element('pwd-captcha-img').src, 'data:image/png;base64,NEWCAPTCHA')
  assert.equal(harness.element('btn-pwd-login').disabled, false)

  first.resolve({ is_enabled: true, uuid: 'old', image: 'data:image/png;base64,OLDCAPTCHA' })
  await flush()
  assert.equal(harness.element('pwd-captcha-img').src, 'data:image/png;base64,NEWCAPTCHA')
  assert.equal(harness.element('pwd-captcha-img').style.display, 'block')
})

test('密码登录请求期间锁定按钮，切换视图后迟到结果不生效', async () => {
  const login = deferred()
  const harness = createHarness({
    fetchCaptcha: async () => ({ is_enabled: true, uuid: 'cap-1', image: 'data:image/png;base64,CAP' }),
    loginWithPassword: () => login.promise,
  })
  await harness.open()
  await harness.element('tab-pwd').dispatch('click')
  await flush()
  harness.element('pwd-username').value = 'student'
  harness.element('pwd-password').value = 'secret'
  harness.element('pwd-captcha').value = '1234'

  const pending = harness.element('btn-pwd-login').dispatch('click')
  await flush()
  assert.equal(harness.loginCalls.length, 1)
  assert.equal(harness.element('btn-pwd-login').disabled, true)
  assert.equal(harness.element('pwd-login-text').textContent, '登录中…')

  await harness.element('btn-pwd-login').dispatch('click')
  await flush()
  assert.equal(harness.loginCalls.length, 1)

  await harness.element('btn-back').dispatch('click')
  login.resolve({ token: { access_token: 'late-token' }, user: { nickname: '迟到账号' } })
  await pending
  await flush()

  assert.equal(harness.saves.length, 0)
  assert.equal(harness.element('view-main').style.display, 'flex')
  assert.equal(harness.element('pwd-login-text').textContent, '立即登录')
})

test('扫码轮询到达五分钟截止后停止并提示重新获取', async () => {
  const harness = createHarness({
    fetchScanQrcode: async () => ({
      scene_id: 'fba_0123456789abcdef',
      qrcode_data_url: 'data:image/png;base64,QR',
      expires_in: 300,
    }),
    pollScanStatus: async () => ({ status: 'PENDING' }),
  })
  await harness.open()
  await harness.element('btn-show-scan').dispatch('click')
  await flush()

  const pollTimer = harness.timers.find(timer => timer.ms === 2000)
  assert.ok(pollTimer)

  harness.clock.offset = 300 * 1000 + 1000
  await pollTimer.fn()

  assert.equal(harness.pollCalls.length, 0)
  assert.equal(harness.element('scan-main-hint').textContent, '二维码已过期，请重新获取')
  assert.equal(harness.timers.filter(timer => timer.ms === 2000).length, 1)
})

test('扫码轮询网络错误显示可恢复提示并继续重试', async () => {
  const harness = createHarness({
    fetchScanQrcode: async () => ({
      scene_id: 'fba_0123456789abcdef',
      qrcode_data_url: 'data:image/png;base64,QR',
      expires_in: 120,
    }),
    pollScanStatus: async () => { throw new Error('网络断开') },
  })
  await harness.open()
  await harness.element('btn-show-scan').dispatch('click')
  await flush()

  const firstTimer = harness.timers.find(timer => timer.ms === 2000)
  assert.ok(firstTimer)
  await firstTimer.fn()
  await flush()

  assert.equal(harness.pollCalls.length, 1)
  assert.match(harness.element('scan-main-hint').textContent, /暂时无法确认授权：网络断开，正在重试/)
  assert.equal(harness.timers.filter(timer => timer.ms === 2000).length, 2)
})

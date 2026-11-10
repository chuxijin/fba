import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'

const read = path => readFile(new URL(path, import.meta.url), 'utf8')

const packageJson = JSON.parse(await read('../package.json'))
const manifest = JSON.parse(await read('../public/manifest.json'))
const popupHtml = await read('../src/popup.html')
const popupTs = await read('../src/popup/popup.ts')
const supportHtml = await read('../src/support.html')
const supportTs = await read('../src/support/support.ts')
const settingsModal = await read('../src/content/ui/SettingsModal.vue')
const floatingWidget = await read('../src/content/ui/FloatingWidget.vue')
const background = await read('../src/background/index.ts')
const auth = await read('../src/utils/auth.ts')
const build = await read('../build.js')

test('版本号在 package.json 与扩展 manifest 中统一，界面不硬编码版本', () => {
  assert.equal(packageJson.version, '1.0.7')
  assert.equal(manifest.version, packageJson.version)
  for (const source of [popupTs, supportTs, floatingWidget]) {
    assert.match(source, /getManifest\(\)\.version/)
  }
  assert.equal(/\b1\.0\.\d+\b/.test(popupTs), false)
  assert.equal(/\b1\.0\.\d+\b/.test(supportTs), false)
})

test('扫码界面不提供假登录入口、测试账号或固定 15 次文案', () => {
  for (const [name, source] of [['popup.html', popupHtml], ['popup.ts', popupTs], ['SettingsModal.vue', settingsModal]]) {
    assert.equal(/测试账号|测试用户|test@|admin\/|mock_confirm|演示模式|假装成功/.test(source), false, name)
    assert.equal(/15\s*次/.test(source), false, name)
  }
  assert.equal(popupHtml.includes('id="btn-dev-fill"'), false)
  assert.equal(/btn-dev-fill/.test(popupTs), false)
  assert.match(popupHtml, /id="btn-scan-retry"[^>]*>重新获取二维码</)
  assert.match(popupTs, /btnScanRetry\.disabled = false/)
  assert.match(popupHtml, /额度以账号实际权益为准/)
})

test('帮助页本地承载，不跳官网，脚本为可执行的模块入口', () => {
  assert.equal(/https?:\/\//.test(supportHtml.split('<script')[0]), false)
  assert.equal(/href="https?:\/\//.test(supportHtml), false)
  assert.match(supportHtml, /<script type="module" src="\/support\/support\.ts"><\/script>/)
  assert.match(supportHtml, /id="feedback-form"/)
  assert.match(supportHtml, /id="history-list"/)
  assert.match(supportHtml, /帮助内容随插件安装，无需访问官网/)
})

test('帮助页用 textContent 渲染反馈内容，避免 HTML 注入', () => {
  assert.equal(/innerHTML/.test(supportTs), false)
  assert.match(supportTs, /paragraph\.textContent = String\(text\)/)
  assert.equal(/document\.referrer|document\.URL|location\.href/.test(supportTs), false)
  assert.match(supportTs, /exportMessage\('SUBMIT_FEEDBACK', \{\s*feedbackType:[^}]*content:[^}]*contact:/)
  assert.equal(/'pageUrl'|'url':/.test(supportTs), false)
})

test('生产构建移除本地官网权限与注入，并保留 support 页构建入口', () => {
  assert.match(build, /manifest\.host_permissions = manifest\.host_permissions\.filter/)
  assert.match(build, /manifest\.content_scripts = manifest\.content_scripts\.filter/)
  assert.match(build, /manifest\.permissions = manifest\.permissions\.filter/)
  assert.match(build, /entry: 'support\.html'/)
  assert.match(build, /生产构建必须使用 HTTPS 后端/)
})

test('二维码只接受真实场景 ID 与位图数据，并固定小程序 mine 页面', () => {
  assert.match(auth, /page=pages%2Fmine%2Findex/)
  assert.match(auth, /data:image\\\/\(png\|jpeg\);base64/)
  assert.match(auth, /登录二维码无效/)
  assert.equal(/mock/i.test(auth), false)
  assert.equal(/svg/i.test(auth), false)
})

test('后台反馈入口固定 support.html#feedback 且反馈消息只允许插件内页面', () => {
  assert.match(background, /chrome\.runtime\.getURL\('support\.html#feedback'\)/)
  assert.match(background, /sender\.url\?\.split\(\/\[\?#\]\/\)\[0\] !== chrome\.runtime\.getURL\('support\.html'\)/)
  assert.equal(/mock_confirm/.test(background), false)
})

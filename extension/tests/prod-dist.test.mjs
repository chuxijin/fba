import assert from 'node:assert/strict'
import test from 'node:test'
import { existsSync } from 'node:fs'
import { readFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const directory = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const dist = resolve(directory, 'dist')
const hasDist = existsSync(resolve(dist, 'manifest.json'))
const skip = hasDist ? false : 'dist 不存在，请先运行 pnpm run build:prod'
const readDist = path => readFile(distFile(path), 'utf8')
const distFile = path => resolve(dist, path.replace(/^\/+/, ''))

const packageJson = JSON.parse(await readFile(resolve(directory, 'package.json'), 'utf8'))

const assetReferences = html => [...html.matchAll(/(?:src|href)="([^"]+)"/g)]
  .map(match => match[1])
  .filter(url => url.startsWith('/assets/') || url.startsWith('/icons/'))

test('dist 清单版本与 package.json 一致', { skip }, async () => {
  const manifest = JSON.parse(await readDist('manifest.json'))
  assert.equal(manifest.manifest_version, 3)
  assert.equal(manifest.version, packageJson.version)
  assert.equal(manifest.version, '1.0.5')
  assert.equal(manifest.background.service_worker, 'background.js')
  assert.equal(manifest.action.default_popup, 'popup.html')
})

test('dist 不申请 localhost 权限，也不再注入官网登录桥', { skip }, async () => {
  const manifest = JSON.parse(await readDist('manifest.json'))
  assert.equal(manifest.host_permissions.some(url => /^http:\/\/(localhost|127\.0\.0\.1)/.test(url)), false)
  assert.ok(manifest.host_permissions.includes('https://api.yzxj.vip/*'))
  assert.equal(manifest.permissions.includes('scripting'), false)
  for (const script of manifest.content_scripts) {
    assert.equal(script.js.includes('site-auth.js'), false)
    assert.equal(script.matches.some(match => /localhost|127\.0\.0\.1/.test(match)), false)
  }
  assert.equal(/(?:^|\n)\s*"scripting"/.test(await readDist('manifest.json')), false)
})

test('dist 保留弹窗、内容脚本、注入脚本与全部图标', { skip }, async () => {
  for (const path of [
    'background.js', 'content.js', 'injected.js', 'popup.html', 'support.html', 'manifest.json',
    'icons/icon16.png', 'icons/icon32.png', 'icons/icon48.png', 'icons/icon128.png',
  ]) assert.ok(existsSync(distFile(path)), path)
})

test('dist 帮助页与弹窗引用的资源真实存在且脚本已编译', { skip }, async () => {
  const supportHtml = await readDist('support.html')
  const popupHtml = await readDist('popup.html')
  for (const [name, html] of [['support.html', supportHtml], ['popup.html', popupHtml]]) {
    const references = assetReferences(html)
    assert.ok(references.length > 0, name)
    for (const reference of references) assert.ok(existsSync(distFile(reference)), `${name} -> ${reference}`)
  }
  assert.match(supportHtml, /id="feedback-form"/)
  assert.match(supportHtml, /id="history-list"/)
  assert.match(supportHtml, /src="\/assets\/support-[^"]+\.js"/)
  assert.equal(/src="\/support\/support\.ts"|\.vue"|\.ts"/.test(supportHtml), false)
})

test('dist 各入口内置 HTTPS 生产 API，不包含假码请求与测试账号文案', { skip }, async () => {
  const popupHtml = await readDist('popup.html')
  const supportHtml = await readDist('support.html')
  const popupAsset = assetReferences(popupHtml).find(url => url.endsWith('.js'))
  const supportAsset = assetReferences(supportHtml).find(url => url.endsWith('.js'))
  // 帮助页只通过后台发送消息，本身不直连后端，因此只校验直连入口。
  const bundles = ['background.js', 'content.js', popupAsset]
  const pages = [...bundles, supportAsset, 'popup.html', 'support.html']

  for (const path of bundles) {
    assert.match(await readDist(path), /https:\/\/api\.yzxj\.vip/, path)
  }
  for (const path of pages) {
    const content = await readDist(path)
    assert.equal(/mock_confirm/.test(content), false, path)
    assert.equal(/测试账号|测试用户/.test(content), false, path)
    assert.equal(/15\s*次/.test(content), false, path)
    assert.equal(/data:image\/svg/.test(content), false, path)
  }
  assert.match(await readDist('background.js'), /support\.html#feedback/)
})

test('dist 清单不再声明任何官网桥接脚本或可访问资源', { skip }, async () => {
  const manifest = JSON.parse(await readDist('manifest.json'))
  assert.equal(JSON.stringify(manifest).includes('site-auth.js'), false)
  assert.equal(JSON.stringify(manifest).includes('localhost'), false)
  assert.equal(JSON.stringify(manifest).includes('127.0.0.1'), false)
})

test('dist 不生成 site-auth.js，也不内嵌任何本地开发地址常量', { skip }, async () => {
  assert.equal(existsSync(distFile('site-auth.js')), false)

  const popupHtml = await readDist('popup.html')
  const supportHtml = await readDist('support.html')
  const popupAsset = assetReferences(popupHtml).find(url => url.endsWith('.js'))
  const supportAsset = assetReferences(supportHtml).find(url => url.endsWith('.js'))
  const pages = [
    'background.js', 'content.js', 'injected.js', popupAsset, supportAsset,
    'popup.html', 'support.html', 'manifest.json',
  ]
  for (const path of pages) {
    const content = await readDist(path)
    assert.equal(/localhost|127\.0\.0\.1|:8000/.test(content), false, path)
  }
})

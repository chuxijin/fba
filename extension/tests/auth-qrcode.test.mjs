import assert from 'node:assert/strict'
import test from 'node:test'
import { importTypeScript } from './helpers/typescript.mjs'

const { fetchScanQrcode, pollScanStatus } = await importTypeScript(new URL('../src/utils/auth.ts', import.meta.url))

const BASE = 'https://api.yzxj.vip'
const PNG = 'data:image/png;base64,iVBORw0KGgo='
const JPEG = 'data:image/jpeg;base64,/9j/4AAQSkZJRg=='
const SCENE = 'fba_0123456789abcdef'
const valid = () => ({ scene_id: SCENE, qrcode_data_url: PNG, expires_in: 120 })
const json = (data, code = 200, status = 200) => new Response(JSON.stringify({ code, data }), { status })
// 直接返回解析结果，避免 JSON 把 Infinity/NaN 归一化成 null。
const payload = (data) => ({ status: 200, ok: true, json: async () => ({ code: 200, data }) })

function capture(response) {
  const requests = []
  globalThis.fetch = async (url, options = {}) => {
    requests.push({ url, options })
    return response()
  }
  return requests
}

test('真实二维码固定打开小程序 mine 页面，接受 PNG/JPEG 数据并按扩展身份请求', async () => {
  const requests = capture(() => json(valid()))
  const result = await fetchScanQrcode(BASE)
  assert.deepEqual(result, valid())
  assert.equal(requests.length, 1)
  assert.equal(requests[0].url, `${BASE}/api/v1/oauth2/wechat/scan/qrcode?page=pages%2Fmine%2Findex`)
  assert.equal(requests[0].options.headers['X-Client-Type'], 'extension')

  const jpeg = capture(() => json({ ...valid(), qrcode_data_url: JPEG }))
  assert.deepEqual(await fetchScanQrcode(BASE), { ...valid(), qrcode_data_url: JPEG })
  assert.equal(jpeg.length, 1)
})

test('拒绝 SVG 及其它非位图二维码，不生成可扫码的假图片', async () => {
  const rejected = [
    'data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=',
    'data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3C%2Fsvg%3E',
    'data:image/gif;base64,R0lGODlhAQABAAAAACw=',
    'data:text/html;base64,PGh0bWw+',
    'https://api.yzxj.vip/qrcode.png',
    'javascript:alert(1)',
  ]
  for (const qrcode_data_url of rejected) {
    capture(() => json({ ...valid(), qrcode_data_url }))
    await assert.rejects(fetchScanQrcode(BASE), /登录二维码无效/, qrcode_data_url)
  }
})

test('拒绝伪造场景 ID、非正过期时间与缺失字段', async () => {
  const rejected = [
    { ...valid(), scene_id: 'scene-1' },
    { ...valid(), scene_id: 'fba_ABCDEF0123456789' },
    { ...valid(), scene_id: undefined },
    { ...valid(), expires_in: 0 },
    { ...valid(), expires_in: -1 },
    { ...valid(), qrcode_data_url: undefined },
  ]
  for (const data of rejected) {
    capture(() => json(data))
    await assert.rejects(fetchScanQrcode(BASE), /登录二维码无效/, JSON.stringify(data))
  }
})

test('二维码有效期必须是有限数字且不超过 300 秒', async () => {
  const rejected = ['120', '300', NaN, Infinity, -Infinity, 301, 300.5, 0]
  for (const expires_in of rejected) {
    capture(() => payload({ ...valid(), expires_in }))
    await assert.rejects(fetchScanQrcode(BASE), /登录二维码无效/, String(expires_in))
  }
  capture(() => payload({ ...valid(), expires_in: 300 }))
  assert.equal((await fetchScanQrcode(BASE)).expires_in, 300)
})

test('二维码失败可重新获取，不缓存上次失败结果', async () => {
  let calls = 0
  globalThis.fetch = async () => {
    calls++
    if (calls === 1) return json({ ...valid(), qrcode_data_url: 'data:image/svg+xml;base64,PHN2Zz4=' })
    return json(valid())
  }
  await assert.rejects(fetchScanQrcode(BASE), /登录二维码无效/)
  assert.deepEqual(await fetchScanQrcode(BASE), valid())
  assert.equal(calls, 2)
})

test('扫码状态按场景 ID 编码请求，返回 PENDING/CONFIRMED/EXPIRED 原文', async () => {
  for (const status of ['PENDING', 'CONFIRMED', 'EXPIRED']) {
    const requests = capture(() => json({ status }))
    assert.deepEqual(await pollScanStatus(SCENE, BASE), { status })
    assert.equal(requests[0].url, `${BASE}/api/v1/oauth2/wechat/scan/status?scene_id=${encodeURIComponent(SCENE)}`)
  }
})

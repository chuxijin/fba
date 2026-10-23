import assert from 'node:assert/strict'
import test from 'node:test'
import { importTypeScript } from './helpers/typescript.mjs'

const { sendAuthMessage, requestAuthApi } = await importTypeScript(new URL('../src/utils/auth.ts', import.meta.url))

test('后台无响应时超时，迟到回调不覆盖结果，下一次请求仍可成功', async () => {
  let respond
  globalThis.chrome = { runtime: { sendMessage(_message, callback) { respond = callback } } }
  await assert.rejects(sendAuthMessage({ type: 'GET_QUOTA' }, '账户超时', 10), /账户超时/)
  respond({ success: true, data: 'late' })
  chrome.runtime.sendMessage = (_message, callback) => callback({ success: true, data: 'ready' })
  assert.equal((await sendAuthMessage({ type: 'GET_QUOTA' }, '账户超时', 10)).data, 'ready')
})

test('扩展上下文失效的同步异常与后台失败都会正常拒绝 Promise', async () => {
  globalThis.chrome = { runtime: { sendMessage() { throw new Error('Extension context invalidated') } } }
  await assert.rejects(sendAuthMessage({ type: 'LOGOUT_AUTH' }, '退出失败'), /context invalidated/)
  chrome.runtime.sendMessage = (_message, callback) => callback({ success: false, error: 'offline' })
  await assert.rejects(sendAuthMessage({ type: 'LOGOUT_AUTH' }, '退出失败'), /offline/)
})

test('密码错误保留后端提示，非 JSON 的 401 仍识别为凭据失效', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ code: 401, msg: '账号或密码错误' }), { status: 401 })
  await assert.rejects(requestAuthApi('/auth/login'), (error) => error.unauthorized && error.message === '账号或密码错误')
  globalThis.fetch = async () => new Response('Unauthorized', { status: 401 })
  await assert.rejects(requestAuthApi('/sys/users/me'), (error) => error.unauthorized)
})

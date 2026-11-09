import { UnifiedPaper, RenderTypographySettings } from '../adapters/types'
import { WrongImportItem } from '../adapters/importer'
import { fenbiReportRoute } from '../adapters/fenbi/report'
import type { PracticeReportPayload } from '../adapters/fenbi/report'
import {
  requestCurrentQuota, getRequestAuthSession, isTokenExpired, clearAuthSessionIfCurrent,
  STORAGE_KEY_QUOTA_REVISION, QuotaInfo,
  STORAGE_KEY_TOKEN, STORAGE_KEY_USER,
} from '../utils/auth'
import { bootstrapSiteSession, handleSiteAuth, logoutExtension, publicSession } from '../utils/auth-bridge'
import { BACKEND_BASE as BACKEND_BASE_URL, isSiteAuthMessage, isTrustedSite, SITE_URL_PATTERNS } from '../utils/auth-protocol'
import { collectAuthDiagnostics } from '../utils/auth-diagnostics'
import { exportRequest, parseDelivery, downloadExportFiles, fetchExportQr } from '../utils/export-delivery'
import { listExtensionFeedback, submitExtensionFeedback } from '../utils/support'


// 监听来自 Content Script 或 Popup 的消息
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'OPEN_SUPPORT') {
    chrome.tabs.create({ url: chrome.runtime.getURL('support.html#feedback') })
      .then(() => sendResponse({ success: true }))
      .catch((error) => sendResponse({ success: false, error: error.message }))
    return true
  }
  if (message.type === 'SUBMIT_FEEDBACK' || message.type === 'LIST_FEEDBACK') {
    if (sender.url?.split(/[?#]/)[0] !== chrome.runtime.getURL('support.html')) {
      sendResponse({ success: false, error: '请从插件意见反馈页面操作' })
      return false
    }
    const task = message.type === 'SUBMIT_FEEDBACK'
      ? submitExtensionFeedback(message.payload)
      : listExtensionFeedback(message.payload?.page)
    task.then(data => sendResponse({ success: true, data }))
      .catch(error => sendResponse({ success: false, error: error.message }))
    return true
  }
  if (message.type === 'GET_AUTH_DIAGNOSTICS' || message.type === 'RECONNECT_SITE_AUTH') {
    if (!sender.url?.startsWith(chrome.runtime.getURL(''))) {
      sendResponse({ success: false, error: '请从扩展弹窗发起同步' })
      return false
    }
    const task = message.type === 'GET_AUTH_DIAGNOSTICS'
      ? collectAuthDiagnostics().then((report) => ({ report }))
      : handleGetQuota().then((data) => ({ data }))
    task
      .then((result) => sendResponse({ success: true, ...result }))
      .catch((error) => sendResponse({ success: false, error: error.message }))
    return true
  }
  if (isSiteAuthMessage(message)) {
    if (!isTrustedSite(sender.url) || sender.frameId !== 0) {
      sendResponse({ success: false, error: '不允许此页面同步登录' })
      return false
    }
    handleSiteAuth(message)
      .then((session) => sendResponse({ success: true, state: publicSession(session) }))
      .catch((error) => sendResponse({ success: false, error: error.message }))
    return true
  }
  if (message.type === 'LOGOUT_AUTH') {
    logoutExtension(message.expectedToken)
      .then(() => sendResponse({ success: true }))
      .catch((error) => sendResponse({ success: false, error: error.message }))
    return true
  }
  if (message.type === 'RENDER_AND_EXPORT') {
    handleRenderAndExport(message.payload)
      .then((res) => sendResponse({ success: true, ...res }))
      .catch((err) => sendResponse({
        success: false, error: err.message,
        ...(err.name === 'TimeoutError' || err.name === 'TypeError' ? { kind: 'unknown' } : {}),
      }))
    return true // 保持异步消息通道开启
  }
  if (message.type === 'GET_RENDER_EXPORT') {
    const ticket = message.payload?.ticket
    if (typeof ticket !== 'string' || !/^[A-Za-z0-9_-]{32}$/.test(ticket)) {
      sendResponse({ success: false, error: '排版任务凭证无效' })
      return false
    }
    exportRequest(`/exports/${ticket}`)
      .then(async (state) => {
        if (state.status === 'succeeded') {
          // 额度提示刷新失败不能阻断已经生成的文件交付。
          await chrome.storage.local.set({ [STORAGE_KEY_QUOTA_REVISION]: crypto.randomUUID() }).catch(() => {})
        }
        sendResponse({ success: true, ...state, ...(state.result ? { delivery: parseDelivery(state.result) } : {}) })
      })
      .catch((err) => sendResponse({
        success: false, error: err.message,
        ...(err.name === 'TimeoutError' || err.name === 'TypeError' ? { kind: 'communication' } : {}),
      }))
    return true
  }
  if (message.type === 'GET_RENDER_QR') {
    fetchExportQr(message.payload?.url)
      .then((image) => sendResponse({ success: true, image }))
      .catch((err) => sendResponse({ success: false, error: err.message }))
    return true
  }
  if (message.type === 'DOWNLOAD_RENDER_FILES') {
    downloadExportFiles(message.payload?.files)
      .then((result) => sendResponse({ success: true, ...result }))
      .catch((err) => sendResponse({ success: false, error: err.message }))
    return true
  }

  if (message.type === 'GET_QUOTA') {
    handleGetQuota()
      .then((data) => sendResponse({ success: true, data }))
      .catch((err) => sendResponse({ success: false, error: err.message }))
    return true
  }

  if (message.type === 'IMPORT_WRONG_QUESTIONS') {
    handleImportWrongQuestions(message.payload, sender)
      .then((res) => sendResponse({ success: true, ...res }))
      .catch((err) => sendResponse({ success: false, error: err.message }))
    return true
  }

  if (message.type === 'IMPORT_PRACTICE_REPORT') {
    const route = fenbiReportRoute(sender.url || '')
    if (sender.frameId !== 0 || !route || message.payload?.source_key !== route.key) {
      sendResponse({ success:false, error:'请从当前粉笔结算页面导入记录' })
      return false
    }
    handleImportPracticeReport(message.payload)
      .then(data => sendResponse({ success:true, ...data }))
      .catch(error => sendResponse({ success:false, error:error.message }))
    return true
  }

  if (message.type === 'UNDO_IMPORT_BATCH') {
    handleUndoImportBatch(message.payload?.importBatchId)
      .then((res) => sendResponse({ success: true, ...res }))
      .catch((err) => sendResponse({ success: false, error: err.message }))
    return true
  }
})

let quotaRequest: Promise<QuotaInfo> | null = null
async function handleImportPracticeReport(payload: PracticeReportPayload) {
  const session = await getRequestAuthSession(BACKEND_BASE_URL)
  const accessToken = session.token?.access_token
  if (!accessToken) throw new Error('请先在插件中登录，再导入练习记录')
  if (isTokenExpired(session.token)) {
    await clearAuthSessionIfCurrent(accessToken)
    throw new Error('登录已过期，请重新登录后再导入')
  }
  const response = await fetch(`${BACKEND_BASE_URL}/api/v1/gk/practice-logs/import-report`, {
    method:'POST', headers:{ 'Content-Type':'application/json', Authorization:`Bearer ${accessToken}` }, body:JSON.stringify(payload),
  })
  const body = await response.json().catch(() => null)
  if (response.status === 401 || body?.code === 401) {
    await clearAuthSessionIfCurrent(accessToken)
    throw new Error('登录已过期，请重新登录')
  }
  if (!response.ok || (body?.code != null && body.code !== 200)) throw new Error(describeBackendError(body, response.status))
  if (!body?.data?.record?.id) throw new Error('服务端未返回记录，请重试确认导入状态')
  return body.data
}
chrome.storage.onChanged.addListener((changes, area) => {
  // 凭据变化由 requestCurrentQuota 重读并重试，后来的视图复用该请求。
  // 导出扣减必须另取最新额度，避免复用扣减前已经开始的查询。
  if (area === 'local' && STORAGE_KEY_QUOTA_REVISION in changes) quotaRequest = null
  if (SITE_URL_PATTERNS.length && area === 'local' && (STORAGE_KEY_TOKEN in changes || STORAGE_KEY_USER in changes)) {
    void chrome.tabs.query({ url: SITE_URL_PATTERNS }).then((tabs) => {
      for (const tab of tabs) {
        if (tab.id && isTrustedSite(tab.url)) {
          void chrome.tabs.sendMessage(tab.id, { type: 'SITE_AUTH_CHANGED' }).catch(() => {})
        }
      }
    }).catch(() => {})
  }
})

function handleGetQuota(): Promise<QuotaInfo> {
  if (quotaRequest) return quotaRequest
  const task = bootstrapSiteSession().then(() => requestCurrentQuota(BACKEND_BASE_URL))
  quotaRequest = task
  void task.finally(() => { if (quotaRequest === task) quotaRequest = null }).catch(() => {})
  return task
}


/**
 * 把错题逐条导入到后端「错题待复盘」。
 *
 * 走 POST /api/v1/qbank-v2/wrong-questions/external（entry_source=import）。
 * 说明：
 *  1. 该接口只挂 JWT，没有 RBAC 与配额闸门，普通登录用户即可调用；
 *  2. 请求体刻意不含 summary / review_data / tag_ids / knowledge_point_ids，
 *     否则后端会把题目直接判为「已复盘」，从待复盘队列里消失；
 *  3. 逐题独立成败：单题失败不阻断批次，最后汇总失败原因。
 */
/** 单次请求最多提交的题目数：与服务端 BATCH_IMPORT_LIMIT(50) 留出余量 */
const IMPORT_CHUNK_SIZE = 20

async function handleImportWrongQuestions(
  payload: { items: WrongImportItem[]; paperTitle?: string },
  sender?: chrome.runtime.MessageSender
) {
  const items = Array.isArray(payload?.items) ? payload.items : []
  if (items.length === 0) throw new Error('没有可导入的错题')

  const session = await getRequestAuthSession(BACKEND_BASE_URL)
  const accessToken = session.token?.access_token
  if (!accessToken) throw new Error('请先在插件中登录，再导入错题库')
  if (isTokenExpired(session.token)) {
    await clearAuthSessionIfCurrent(accessToken)
    throw new Error('登录已过期，请重新登录后再导入')
  }

  // 分片提交：所有分片共用同一个批次 ID，保证可以在小程序里整批撤销
  const batchId = createImportBatchId()
  const tabId = sender?.tab?.id
  const total = items.length
  let imported = 0
  let created = 0
  let reused = 0
  let hasBreakdown = true
  let failed = 0
  let firstError = ''
  const importedKeys: string[] = []
  const duplicateKeys: string[] = []

  for (let offset = 0; offset < items.length; offset += IMPORT_CHUNK_SIZE) {
    const chunk = items.slice(offset, offset + IMPORT_CHUNK_SIZE)
    const data = await postWrongQuestions(chunk, accessToken, batchId)

    const resultItems: any[] = Array.isArray(data?.items) ? data.items : []
    for (const item of resultItems) {
      if (typeof item?.external_key === 'string' && item.external_key) importedKeys.push(item.external_key)
    }

    const failures: any[] = Array.isArray(data?.failures) ? data.failures : []
    for (const failure of failures) {
      const reason = String(failure?.reason || '')
      if (reason.includes('已导入过')) {
        if (typeof failure?.external_key === 'string' && failure.external_key) duplicateKeys.push(failure.external_key)
      } else if (!firstError) {
        firstError = reason
      }
    }

    imported += Number(data?.succeeded ?? resultItems.length)
    if (typeof data?.created === 'number' && typeof data?.reused === 'number') {
      created += data.created
      reused += data.reused
    } else {
      hasBreakdown = false
    }
    failed += Number(data?.failed ?? failures.length)

    // 逐片回传进度，悬浮窗据此显示「正在导入 20/38」
    if (tabId != null) {
      void chrome.tabs
        .sendMessage(tabId, {
          type: 'IMPORT_PROGRESS',
          payload: { done: offset + chunk.length, total, imported, failed, ...(hasBreakdown ? { created, reused } : {}) },
        })
        .catch(() => {})
    }
  }

  // 「已导入过」不算失败：题目本来就在库里
  const realFailed = Math.max(failed - duplicateKeys.length, 0)
  const allDuplicates = imported === 0 && realFailed === 0 && duplicateKeys.length > 0

  return {
    importBatchId: batchId,
    total,
    imported,
    ...(hasBreakdown ? { created, reused } : {}),
    failed: realFailed,
    importedKeys,
    duplicateKeys,
    allDuplicates,
    error: realFailed > 0 ? `${realFailed} 道导入失败${firstError ? `：${firstError}` : ''}` : undefined,
  }
}

/** 生成一次导入的批次 ID（32 位十六进制，满足后端 8~64 位约束） */
function createImportBatchId(): string {
  try {
    return crypto.randomUUID().replace(/-/g, '')
  } catch {
    return `b${Date.now().toString(16)}${Math.random().toString(16).slice(2, 12)}`
  }
}

/** 按批次撤销一次扩展导入 */
async function handleUndoImportBatch(importBatchId?: string) {
  const batchId = String(importBatchId || '').trim()
  if (!batchId) throw new Error('缺少导入批次 ID，无法撤销')

  const session = await getRequestAuthSession(BACKEND_BASE_URL)
  const accessToken = session.token?.access_token
  if (!accessToken) throw new Error('请先登录后再撤销')
  if (isTokenExpired(session.token)) {
    await clearAuthSessionIfCurrent(accessToken)
    throw new Error('登录已过期，请重新登录后再撤销')
  }

  const res = await fetch(
    `${BACKEND_BASE_URL}/api/v1/qbank-v2/wrong-questions/import-batches/${encodeURIComponent(batchId)}`,
    {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${accessToken}` },
    }
  )

  const rawText = await res.text().catch(() => '')
  let parsed: any = null
  try {
    parsed = rawText ? JSON.parse(rawText) : null
  } catch {}

  if (res.status === 401) {
    await clearAuthSessionIfCurrent(accessToken)
    throw new Error('登录已过期，请重新登录')
  }
  if (!res.ok) {
    throw new Error(describeBackendError(parsed, res.status))
  }
  if (parsed && parsed.code !== undefined && parsed.code !== 200) {
    throw new Error(parsed.msg || '撤销失败')
  }

  return {
    deletedStates: Number(parsed?.data?.deleted_states || 0),
    deletedQuestions: Number(parsed?.data?.deleted_questions || 0),
    detachedStates: Number(parsed?.data?.detached_states || 0),
  }
}

/** 提交一片错题；失败时抛出可直接展示的错误信息 */
async function postWrongQuestions(items: WrongImportItem[], accessToken: string, importBatchId?: string) {
  // order 仅用于前端定位，不能出现在后端请求体里
  const body = items.map(({ order: _order, ...rest }) => rest)

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${accessToken}`,
  }
  // 分片提交时用同一批次 ID，后端据此把多片归入同一批次
  if (importBatchId) headers['X-Import-Batch-Id'] = importBatchId

  const res = await fetch(`${BACKEND_BASE_URL}/api/v1/qbank-v2/wrong-questions/external`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })

  // 只读一次 body：先 text 再本地解析，避免 res.json() 抛 "body stream already read"
  const rawText = await res.text().catch(() => '')
  let parsed: any = null
  try {
    parsed = rawText ? JSON.parse(rawText) : null
  } catch {}

  if (res.status === 401) {
    await clearAuthSessionIfCurrent(accessToken)
    throw new Error('登录已过期，请重新登录')
  }
  if (!res.ok) {
    throw new Error(describeBackendError(parsed, res.status))
  }
  if (parsed && parsed.code !== undefined && parsed.code !== 200) {
    throw new Error(parsed.msg || '后端拒绝了本次导入')
  }
  return parsed?.data
}

/** 把后端错误响应翻译成一句话：兼容 FastAPI 的 detail 数组（422 校验错误） */
function describeBackendError(parsed: any, status: number): string {
  const detail = parsed?.detail
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0]
    const field = Array.isArray(first?.loc) ? first.loc[first.loc.length - 1] : ''
    return `字段校验失败（${field}）：${first?.msg || '参数不合法'}`
  }
  if (typeof detail === 'string' && detail) return detail
  if (typeof parsed?.msg === 'string' && parsed.msg) return parsed.msg
  return `导入接口响应异常(${status})`
}


/**
 * 处理排版与导出核心流水线
 */
async function handleRenderAndExport(payload: {
  paper: UnifiedPaper
  settings: RenderTypographySettings
  target: 'computer_download' | 'mobile_sync'
  retryTicket?: string
}) {
  const { paper, settings, target } = payload

  try {
    // 1. 构建公开免登录排版请求 Payload
    const publicPayload = {
      paper: paper,
      options: {
        include_answer: settings.includeAnswer,
        answer_placement: settings.answerPlacement || 'merged',
        output_format: settings.outputFormat || 'pdf',
      },
      target: target,
      ...(payload.retryTicket ? { retry_ticket: payload.retryTicket } : {}),
    }


    // 1. 读取本地登录凭据 (若已登录则享有每日高额特权)
    const session = await getRequestAuthSession(BACKEND_BASE_URL)
    const accessToken = session.token?.access_token
    if (accessToken && isTokenExpired(session.token)) {
      await clearAuthSessionIfCurrent(accessToken)
      throw new Error('登录已过期，请重新登录后排版')
    }

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Render-Client': await getExportClientId(),
    }
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`
    }

    const res = await fetch(`${BACKEND_BASE_URL}/api/v1/render-books/public/exports`, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(publicPayload),
      signal: AbortSignal.timeout(20000),
    })

    if (!res.ok) {
      if (res.status === 404) throw new Error('排版服务尚未更新到此插件版本，请联系维护者完成后端更新；本次未开始排版')
      if (res.status === 401 && accessToken) await clearAuthSessionIfCurrent(accessToken)
      // 只读一次 body：先取 text 再本地解析，避免 res.json() 失败后 res.text() 抛 "body stream already read"
      const rawText = await res.text().catch(() => '')
      let errMsg = `排版服务响应异常(${res.status})`
      try {
        const errJson = JSON.parse(rawText)
        errMsg = errJson.msg || errJson.detail || errMsg
      } catch {
        if (rawText) errMsg = rawText.slice(0, 300)
      }
      throw new Error(errMsg)
    }

    const resJson = await res.json()
    if (resJson.code === 401 && accessToken) await clearAuthSessionIfCurrent(accessToken)
    if (resJson.code !== undefined && resJson.code !== 200) {
      throw new Error(resJson.msg || '排版服务响应异常')
    }
    const jobResult = resJson.data || resJson
    if (typeof jobResult.ticket !== 'string' || !/^[A-Za-z0-9_-]{32}$/.test(jobResult.ticket))
      throw new Error('排版服务未返回任务凭证')
    return { ticket: jobResult.ticket, ...(jobResult.reused ? { reused: true } : {}) }
  } catch (error: any) {
    console.error('[Background] 考场排版接口请求失败:', error)
    // 彻底废除假装成功的演示模式，真实抛出错误，触发弹窗的错误重试视图
    throw error instanceof Error ? error : new Error('排版服务响应异常，请稍后再获取结果。')
  }
}

let exportClientRequest: Promise<string> | null = null
function getExportClientId(): Promise<string> {
  if (exportClientRequest) return exportClientRequest
  const task = (async () => {
    const key = 'fba_render_client_id'
    const stored = await chrome.storage.local.get([key])
    if (typeof stored[key] === 'string' && /^[a-f0-9]{32}$/.test(stored[key])) return stored[key]
    const value = crypto.randomUUID().replace(/-/g, '')
    await chrome.storage.local.set({ [key]: value })
    return value
  })()
  exportClientRequest = task
  void task.finally(() => { if (exportClientRequest === task) exportClientRequest = null }).catch(() => {})
  return task
}

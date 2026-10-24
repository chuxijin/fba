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


// 监听来自 Content Script 或 Popup 的消息
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
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
      .catch((err) => sendResponse({ success: false, error: err.message }))
    return true // 保持异步消息通道开启
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
  if (area === 'local' && (STORAGE_KEY_TOKEN in changes || STORAGE_KEY_USER in changes)) {
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
    failed += Number(data?.failed ?? failures.length)

    // 逐片回传进度，悬浮窗据此显示「正在导入 20/38」
    if (tabId != null) {
      void chrome.tabs
        .sendMessage(tabId, {
          type: 'IMPORT_PROGRESS',
          payload: { done: offset + chunk.length, total, imported, failed },
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
    }
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`
    }

    const res = await fetch(`${BACKEND_BASE_URL}/api/v1/render-books/public/reformat`, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(publicPayload),
    })

    if (!res.ok) {
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
    // 导出扣减后通知所有已打开的账户视图重新确认额度。
    await chrome.storage.local.set({ [STORAGE_KEY_QUOTA_REVISION]: crypto.randomUUID() })

    // 2. 根据目标分支进行交付
    if (target === 'computer_download') {
      const rawDl = jobResult.download_url
      if (!rawDl) throw new Error('后端未返回下载地址（download_url 为空），请联系管理员排查排版服务')
      const downloadUrl = rawDl.startsWith('http') ? rawDl : `${BACKEND_BASE_URL}${rawDl}`
      const isMistake = paper.metadata?.scene === 'mistake' || paper.title?.includes('错题')
      const tag = isMistake ? '【粉笔错题】' : '【粉笔真题】'
      const fallbackName = `${tag}${sanitizeFileName(paper.title)} (共${paper.total_questions || 10}题).${settings.outputFormat || 'pdf'}`
      // 后端返回的 file_name 同样必须清洗：Chrome 遇到 / : ? 等非法字符会直接拒绝下载且不给明确提示
      const fileName = sanitizeFileName(jobResult.file_name || fallbackName)

      // 必须 await 并检查 lastError，否则下载失败只会变成 SW 里的 unhandled rejection，UI 却报“已开始下载”
      const mainFile = await downloadAndVerify(downloadUrl, fileName)

      // 额外分册（如答案解析册）串行 await 下载：MV3 SW 里 setTimeout 延迟极易在休眠时丢失
      const extraFiles: { fileName: string; savedPath?: string }[] = []
      if (Array.isArray(jobResult.extra_files)) {
        for (const ef of jobResult.extra_files) {
          if (!ef?.download_url) continue
          const efUrl = ef.download_url.startsWith('http') ? ef.download_url : `${BACKEND_BASE_URL}${ef.download_url}`
          const efName = sanitizeFileName(ef.file_name || '答案解析册.pdf')
          try {
            const efRes = await downloadAndVerify(efUrl, efName)
            extraFiles.push({ fileName: efName, savedPath: efRes.savedPath })
          } catch (efErr: any) {
            // 分册失败不阻断主文件交付，但要留痕
            console.warn('[Background] 附加分册下载失败:', efName, efErr?.message)
          }
        }
      }

      return {
        downloadUrl,
        fileName,
        savedPath: mainFile.savedPath,
        hasExtraFiles: extraFiles.length > 0,
        extraFiles,
        remainingQuota: jobResult.remaining_quota,
      }
    } else {
      // 导出到手机：返回该任务专属的小程序码链接
      const rawQr = jobResult.qr_code_url
      if (!rawQr) throw new Error('后端未返回小程序码链接（qr_code_url 为空）')
      const qrCodeUrl = rawQr.startsWith('http') ? rawQr : `${BACKEND_BASE_URL}${rawQr}`
      return {
        jobId: jobResult.job_id,
        qrCodeUrl,
        remainingQuota: jobResult.remaining_quota,
      }
    }
  } catch (error: any) {
    console.error('[Background] 考场排版接口请求失败:', error)
    // 彻底废除假装成功的演示模式，真实抛出错误，触发弹窗的错误重试视图
    throw new Error(error?.message || '排版服务响应异常，请确认后端已启动。')
  }
}

/**
 * 发起下载并确认浏览器真的接收了，失败时抛出可直接展示给用户的错误。
 *
 * 为什么必须这样做：
 *  1. chrome.downloads.download 在文件名非法、host 被拒等情况下只通过 lastError 返回错误，
 *     不 await / 不读 lastError 的话，失败会变成未处理的 Promise rejection，UI 却显示“已开始下载”；
 *  2. 下载链接 404（token 过期）也是“秒失败”，探测一次状态即可捕获；
 *  3. 返回真实保存路径，解决“浏览器设置了自定义下载目录 / 开启下载前询问，用户找不到文件”。
 */
async function downloadAndVerify(url: string, filename: string): Promise<{ downloadId: number; savedPath?: string }> {
  const downloadId = await new Promise<number>((resolve, reject) => {
    try {
      chrome.downloads.download({ url, filename, saveAs: false }, (id) => {
        const err = chrome.runtime.lastError
        if (err || typeof id !== 'number') {
          reject(new Error(`浏览器拒绝下载「${filename}」：${err?.message || '未返回下载任务 ID'}`))
          return
        }
        resolve(id)
      })
    } catch (e: any) {
      reject(new Error(`发起下载失败：${e?.message || e}`))
    }
  })

  // 留 1.2s 让浏览器完成入队/握手，捕捉即时失败（token 失效 404、保存目录不可写等）
  await new Promise((r) => setTimeout(r, 1200))
  const item = await new Promise<chrome.downloads.DownloadItem | undefined>((resolve) => {
    chrome.downloads.search({ id: downloadId }, (items) => resolve(items?.[0]))
  })

  if (item?.state === 'interrupted') {
    throw new Error(`下载失败：${describeDownloadError(item.error)}（文件：${filename}）`)
  }
  return { downloadId, savedPath: item?.filename }
}

/** 把 chrome.downloads 的断点原因翻译成人话，直接给用户看 */
function describeDownloadError(code?: string): string {
  const map: Record<string, string> = {
    SERVER_BAD_CONTENT: '服务器返回的文件无效（下载链接可能已过期，请重新排版）',
    SERVER_UNAUTHORIZED: '下载鉴权失败',
    SERVER_FORBIDDEN: '下载被服务器拒绝',
    SERVER_UNREACHABLE: '连不上本地排版服务，请确认后端已启动',
    NETWORK_FAILED: '网络错误',
    NETWORK_TIMEOUT: '网络超时',
    USER_CANCELED: '下载被取消（浏览器弹出了“保存位置”对话框但未确认）',
    FILE_ACCESS_DENIED: '没有权限写入保存目录',
    FILE_NO_SPACE: '磁盘空间不足',
    FILE_NAME_TOO_LONG: '文件名过长',
    FILE_FAILED: '文件写入失败',
    CRASH: '下载进程异常',
  }
  if (!code) return '浏览器中断了下载（未知原因）'
  return `${map[code] || '未知错误'}（${code}）`
}

function sanitizeFileName(name: string): string {
  // Chrome 的 downloads.filename 不接受非法字符与首尾空白/点，同时限制长度避免 FILE_NAME_TOO_LONG
  const cleaned = (name || '')
    .replace(/[\\/:*?"<>|\r\n\t]/g, '_')
    .replace(/^[\s.]+|[\s.]+$/g, '')
    .slice(0, 180)
  return cleaned || '未命名试卷.pdf'
}

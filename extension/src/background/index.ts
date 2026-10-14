import { UnifiedPaper, RenderTypographySettings } from '../adapters/types'

const BACKEND_BASE_URL = 'http://127.0.0.1:8000'

console.log('[公考内容排版] Background Service Worker 启动')

// 监听扩展安装/更新
chrome.runtime.onInstalled.addListener(() => {
  console.log('[公考内容排版] 扩展安装就绪')
})

// 监听来自 Content Script 或 Popup 的消息
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
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
})

async function handleGetQuota() {
  const tokenStore = await chrome.storage.local.get(['fba_auth_token'])
  const accessToken = tokenStore?.fba_auth_token?.access_token

  const headers: Record<string, string> = {}
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`
  }

  const res = await fetch(`${BACKEND_BASE_URL}/api/v1/render-books/public/quota`, {
    headers,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const json = await res.json()
  return json?.data || json
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

    console.log('[Background] 正在请求公开考场排版接口:', publicPayload)

    // 1. 读取本地登录凭据 (若已登录则享有每日高额特权)
    const tokenStore = await chrome.storage.local.get(['fba_auth_token'])
    const accessToken = tokenStore?.fba_auth_token?.access_token

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
      let errMsg = `排版服务响应异常(${res.status})`
      try {
        const errJson = await res.json()
        errMsg = errJson.msg || errJson.detail || errMsg
      } catch {
        const errText = await res.text()
        if (errText) errMsg = errText
      }
      throw new Error(errMsg)
    }

    const resJson = await res.json()
    const jobResult = resJson.data || resJson
    console.log('[Background] 考场排版生成成功:', jobResult)

    // 2. 根据目标分支进行交付
    if (target === 'computer_download') {
      const rawDl = jobResult.download_url
      const downloadUrl = rawDl.startsWith('http') ? rawDl : `${BACKEND_BASE_URL}${rawDl}`
      const isMistake = paper.metadata?.scene === 'mistake' || paper.title?.includes('错题')
      const tag = isMistake ? '【粉笔错题】' : '【粉笔真题】'
      const fallbackName = `${tag}${sanitizeFileName(paper.title)} (共${paper.total_questions || 10}题).${settings.outputFormat || 'pdf'}`
      const fileName = jobResult.file_name || fallbackName


      // 调用 Chrome 原生下载管理器保存主试卷
      chrome.downloads.download({
        url: downloadUrl,
        filename: fileName,
        saveAs: false,
      })

      // 若存在额外分册文件（如答案解析分册），顺延触发下载
      if (jobResult.extra_files && Array.isArray(jobResult.extra_files)) {
        for (const ef of jobResult.extra_files) {
          const efUrl = ef.download_url.startsWith('http') ? ef.download_url : `${BACKEND_BASE_URL}${ef.download_url}`
          setTimeout(() => {
            chrome.downloads.download({
              url: efUrl,
              filename: ef.file_name,
              saveAs: false,
            })
          }, 400)
        }
      }

      return {
        downloadUrl,
        fileName,
        hasExtraFiles: Boolean(jobResult.extra_files?.length),
        remainingQuota: jobResult.remaining_quota ?? 4,
      }
    } else {
      // 导出到手机：返回该任务专属的小程序码链接
      const rawQr = jobResult.qr_code_url
      const qrCodeUrl = rawQr && rawQr.startsWith('http') ? rawQr : `${BACKEND_BASE_URL}${rawQr}`
      return {
        jobId: jobResult.job_id,
        qrCodeUrl,
        remainingQuota: jobResult.remaining_quota ?? 4,
      }
    }
  } catch (error: any) {
    console.error('[Background] 考场排版接口请求失败:', error)
    // 彻底废除假装成功的演示模式，真实抛出错误，触发弹窗的错误重试视图
    throw new Error(error?.message || '排版服务响应异常，请确认后端已启动。')
  }
}

function sanitizeFileName(name: string): string {
  return name.replace(/[\\/:*?"<>|]/g, '_').trim()
}

import type { ExportDelivery, ExportFile } from './export-delivery'

export class ExportFlowError extends Error {
  constructor(message: string, public kind: 'communication' | 'unknown' | 'failed' | 'request', public ticket?: string) {
    super(message)
  }
}

function communicationError(message: string) {
  const updated = /context invalidated/i.test(message)
  return new ExportFlowError(updated
    ? '检测到插件刚刚更新，请按 F5 刷新题库网页，再获取排版结果。'
    : '插件连接暂时中断，排版可能已提交。请继续获取结果，不要重复排版。', 'communication')
}

export async function exportMessage(type: string, payload: unknown): Promise<any> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(communicationError('timeout')), 25000)
    try {
      chrome.runtime.sendMessage({ type, payload }, (response) => {
        clearTimeout(timer)
        const error = chrome.runtime.lastError
        if (error) reject(communicationError(error.message || ''))
        else if (!response?.success) {
          if (response?.kind === 'communication') reject(communicationError(response.error || ''))
          else reject(new ExportFlowError(response?.kind === 'unknown'
            ? '暂时未能确认排版服务的回复，任务可能已提交，请继续获取结果或查看我的题本。'
            : response?.error || '插件通信失败', response?.kind || 'request'))
        }
        else resolve(response)
      })
    } catch (error: any) { clearTimeout(timer); reject(communicationError(error?.message || '')) }
  })
}

/** 每条消息只做一次短请求，长排版不占住 MV3 service worker 的 fetch。 */
export async function waitForExport(ticket: string, isCurrent: () => boolean): Promise<ExportDelivery> {
  const deadline = Date.now() + 20 * 60 * 1000
  let interruptions = 0
  while (Date.now() < deadline && isCurrent()) {
    let state
    try {
      state = await exportMessage('GET_RENDER_EXPORT', { ticket })
      interruptions = 0
    } catch (error: any) {
      // 只重试只读状态查询，绝不因丢包自动重提排版或下载。
      if (error?.kind !== 'communication' || ++interruptions > 3) throw error
      await new Promise(resolve => setTimeout(resolve, 1500))
      continue
    }
    if (!isCurrent()) throw new Error('已切换页面，本次排版结果不再展示')
    if (state.status === 'succeeded' && state.delivery) return state.delivery
    if (state.status === 'failed') throw new ExportFlowError(state.message || '排版失败，请重试', 'failed', ticket)
    if (state.status !== 'running') throw new ExportFlowError(state.message || '暂时无法确认排版结果，请先查看我的题本', 'unknown', ticket)
    await new Promise(resolve => setTimeout(resolve, 1500))
  }
  throw new ExportFlowError('暂时未能确认排版结果，请继续获取结果，或在同一账号的我的题本查看。', 'unknown', ticket)
}

export async function requestFileDownloads(files: ExportFile[]) {
  try { return await exportMessage('DOWNLOAD_RENDER_FILES', { files }) }
  catch (error: any) {
    return { failedFiles: files, downloadWarning: error?.message || '浏览器下载失败', downloadStarted: false }
  }
}

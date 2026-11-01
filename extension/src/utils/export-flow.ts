import type { ExportDelivery, ExportFile } from './export-delivery'

export async function exportMessage(type: string, payload: unknown): Promise<any> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('插件通信超时，请确认网络后重试')), 25000)
    try {
      chrome.runtime.sendMessage({ type, payload }, (response) => {
        clearTimeout(timer)
        const error = chrome.runtime.lastError
        if (error || !response?.success) reject(new Error(error?.message || response?.error || '插件通信失败'))
        else resolve(response)
      })
    } catch (error) { clearTimeout(timer); reject(error) }
  })
}

/** 每条消息只做一次短请求，长排版不占住 MV3 service worker 的 fetch。 */
export async function waitForExport(ticket: string, isCurrent: () => boolean): Promise<ExportDelivery> {
  const deadline = Date.now() + 20 * 60 * 1000
  while (Date.now() < deadline && isCurrent()) {
    const state = await exportMessage('GET_RENDER_EXPORT', { ticket })
    if (!isCurrent()) throw new Error('已切换页面，本次排版结果不再展示')
    if (state.status === 'succeeded' && state.delivery) return state.delivery
    if (state.status === 'failed') throw new Error(state.message || '排版失败，请重试')
    if (state.status !== 'running') throw new Error('排版任务状态异常')
    await new Promise(resolve => setTimeout(resolve, 1500))
  }
  throw new Error('排版等待已结束，请稍后在我的题本查看')
}

export async function requestFileDownloads(files: ExportFile[]) {
  try { return await exportMessage('DOWNLOAD_RENDER_FILES', { files }) }
  catch (error: any) {
    return { failedFiles: files, downloadWarning: error?.message || '浏览器下载失败', downloadStarted: false }
  }
}

import { BACKEND_BASE } from './auth-protocol'

export interface ExportFile { downloadUrl: string; fileName: string }
export interface ExportDelivery {
  files: ExportFile[]
  qrCodeUrl: string
  jobId: string
  remainingQuota?: number
}

export interface DeliveryView {
  files?: ExportFile[]
  reused?: boolean
  qrCodeUrl?: string
  savedPath?: string
  remainingQuota?: number
  failedFiles?: ExportFile[]
  downloadWarning?: string
  downloadStarted?: boolean
}

export async function fetchExportQr(raw: string): Promise<string> {
  const response = await fetch(exportUrl(raw, 'minicode'), { signal: AbortSignal.timeout(20000) })
  const mime = response.headers.get('content-type')?.split(';')[0]
  if (!response.ok || !['image/png', 'image/jpeg'].includes(mime || ''))
    throw new Error('小程序码暂时不可用，请稍后重试')
  const bytes = new Uint8Array(await response.arrayBuffer())
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return `data:${mime};base64,${btoa(binary)}`
}

/** 下载凭证只允许本后端的公开下载路径，不接受网页传来的任意网址。 */
export function exportUrl(raw: string, kind: 'download' | 'minicode'): string {
  const url = new URL(raw, `${BACKEND_BASE}/`)
  const prefix = `/api/v1/render-books/public/${kind}/`
  const suffix = url.pathname.slice(prefix.length)
  if (url.origin !== new URL(BACKEND_BASE).origin || url.username || url.password
    || !url.pathname.startsWith(prefix) || !/^[A-Za-z0-9_-]+$/.test(suffix) || url.search || url.hash)
    throw new Error('排版服务返回了无效的交付地址')
  return url.href
}

export async function exportRequest(path: string, init: RequestInit = {}) {
  const response = await fetch(`${BACKEND_BASE}/api/v1/render-books/public${path}`, {
    ...init, signal: AbortSignal.timeout(20000),
  })
  const body = await response.json().catch(() => null)
  if (response.status === 404 && path.startsWith('/exports')) {
    const message = typeof body?.msg === 'string' && !['Not Found', '请求错误'].includes(body.msg) ? body.msg : ''
    throw new Error(message || '排版服务尚未就绪，请联系维护者确认服务版本；不要重复提交')
  }
  if (!response.ok || !body || (body.code !== undefined && body.code !== 200))
    throw new Error(body?.msg || body?.detail || `排版服务响应异常(${response.status})`)
  return body.data ?? body
}

export function parseDelivery(result: any): ExportDelivery {
  if (!result?.download_url || !result?.file_name || !result?.qr_code_url || !result?.job_id)
    throw new Error('排版服务未返回完整交付信息')
  const files = [{ downloadUrl: exportUrl(result.download_url, 'download'), fileName: result.file_name }]
  for (const file of result.extra_files || []) {
    if (!file.download_url || !file.file_name) throw new Error('分册交付信息不完整')
    files.push({ downloadUrl: exportUrl(file.download_url, 'download'), fileName: file.file_name })
  }
  return { files, qrCodeUrl: exportUrl(result.qr_code_url, 'minicode'), jobId: result.job_id, remainingQuota: result.remaining_quota }
}

export function sanitizeFileName(name: string): string {
  const cleaned = (name || '').replace(/[\\/:*?"<>|\r\n\t]/g, '_').replace(/^[\s.]+|[\s.]+$/g, '')
  const suffix = cleaned.match(/\.(pdf|docx)$/i)?.[0] || ''
  return (cleaned.length > 180 && suffix
    ? `${cleaned.slice(0, 180 - suffix.length)}${suffix}`
    : cleaned.slice(0, 180)) || '未命名试卷.pdf'
}

export async function downloadExportFile(file: ExportFile): Promise<string | undefined> {
  const url = exportUrl(file.downloadUrl, 'download')
  const filename = sanitizeFileName(file.fileName)
  const id = await new Promise<number>((resolve, reject) => {
    chrome.downloads.download({ url, filename, saveAs: false }, (downloadId) => {
      const error = chrome.runtime.lastError
      if (error || typeof downloadId !== 'number') reject(new Error(error?.message || '浏览器未创建下载任务'))
      else resolve(downloadId)
    })
  })
  await new Promise(resolve => setTimeout(resolve, 1200))
  const item = await new Promise<chrome.downloads.DownloadItem | undefined>((resolve, reject) => {
    chrome.downloads.search({ id }, (items) => {
      const error = chrome.runtime.lastError
      if (error) reject(new Error(error.message || '无法确认浏览器下载状态'))
      else resolve(items?.[0])
    })
  })
  if (!item) throw new Error('浏览器下载记录不可用，请打开下载列表确认')
  if (item.state === 'interrupted') throw new Error(`浏览器下载中断：${item.error || '未知原因'}，可重试下载，无需重新排版`)
  return item.filename
}

export async function downloadExportFiles(files: ExportFile[]) {
  if (!Array.isArray(files) || !files.length || files.length > 2) throw new Error('下载文件列表无效')
  // 先校验所有地址，再开始下载，防止部分恶意输入造成副作用。
  for (const file of files) exportUrl(file.downloadUrl, 'download')
  const failedFiles: ExportFile[] = []
  const warnings: string[] = []
  let savedPath: string | undefined
  for (const file of files) {
    try {
      const path = await downloadExportFile(file)
      savedPath ||= path
    }
    catch (error: any) { failedFiles.push(file); warnings.push(`${file.fileName}：${error?.message || '下载失败'}`) }
  }
  return { savedPath, failedFiles, downloadWarning: warnings.join('；'), downloadStarted: failedFiles.length < files.length }
}

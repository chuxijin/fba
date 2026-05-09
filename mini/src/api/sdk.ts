import { setupSdk, getSdkInstance } from '@fba/api-sdk/runtime'
import * as g from '@fba/api-sdk/generated'
import { getEnvBaseUrl } from '@/utils'
import { toLoginPage } from '@/utils/toLoginPage'

function getStoredAccessToken(): string {
  const directToken = uni.getStorageSync('access_token')
  if (directToken) {
    return directToken
  }

  const tokenStoreCache = uni.getStorageSync('token')
  if (!tokenStoreCache) {
    return ''
  }

  try {
    if (typeof tokenStoreCache === 'string') {
      const parsed = JSON.parse(tokenStoreCache)
      return parsed?.tokenInfo?.token || parsed?.tokenInfo?.accessToken || ''
    }
    return tokenStoreCache?.tokenInfo?.token || tokenStoreCache?.tokenInfo?.accessToken || ''
  }
  catch {
    return ''
  }
}

function sanitizeRequestValue<T = unknown>(value: T): T | undefined {
  if (value === undefined || value === 'undefined') {
    return undefined
  }

  if (Array.isArray(value)) {
    return value
      .map(item => sanitizeRequestValue(item))
      .filter(item => item !== undefined) as T
  }

  if (value && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
      .map(([key, item]) => [key, sanitizeRequestValue(item)] as const)
      .filter(([, item]) => item !== undefined)

    return Object.fromEntries(entries) as T
  }

  return value
}

function appendQuery(url: string, params?: Record<string, unknown>) {
  const sanitizedParams = sanitizeRequestValue(params)
  if (!sanitizedParams || Object.keys(sanitizedParams).length === 0) {
    return url
  }

  const search = Object.entries(sanitizedParams)
    .flatMap(([key, value]) => {
      if (Array.isArray(value)) {
        return value.map(item => [key, item] as const)
      }
      return [[key, value] as const]
    })
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join('&')

  if (!search) {
    return url
  }

  return `${url}${url.includes('?') ? '&' : '?'}${search}`
}

function uniAxiosAdapter(config: any) {
  return new Promise((resolve, reject) => {
    const method = String(config.method || 'GET').toUpperCase()
    const fullUrl = appendQuery(`${config.baseURL || ''}${config.url || ''}`, config.params)

    uni.request({
      url: fullUrl,
      method: method as UniApp.RequestOptions['method'],
      data: method === 'GET' ? undefined : sanitizeRequestValue(config.data),
      header: config.headers,
      timeout: config.timeout,
      success: (response) => {
        resolve({
          data: response.data,
          status: response.statusCode,
          statusText: String(response.statusCode),
          headers: response.header,
          config,
          request: response,
        })
      },
      fail: reject,
    })
  })
}

// hey-api 生成方法 URL 已自带 /api/v1 前缀, 因此只用 host 作 baseURL
const sdkBaseURL = import.meta.env.VITE_API_BASE_URL || getEnvBaseUrl() || 'http://127.0.0.1:8000'

export const sdkReady: Promise<void> = setupSdk({
  baseURL: sdkBaseURL,
  adapter: uniAxiosAdapter as any,
  getToken: () => getStoredAccessToken(),
  onUnauthorized: () => toLoginPage(),
}).then(() => undefined)

export const api = g
export { getSdkInstance }

/**
 * 构造题本 PDF/log 等产物的下载相对路径 (不含 host 前缀)。
 * 调用方通常再用 toAbsoluteApiUrl 拼出完整地址用于 uni.downloadFile。
 *
 * 注: 这里走自定义路径而非 SDK 生成方法, 因为返回值会作为字符串塞进 uni.downloadFile,
 * 而非通过 axios 发请求。如果将来后端改路径, 需要同步更新这里。
 */
export function buildRenderBookFileUrl(
  jobId: string,
  fileKind: string,
  options?: {
    inline?: boolean
    prefer_url?: boolean
    render_variant?: string
  },
): string {
  const search = Object.entries({
    inline: options?.inline,
    prefer_url: options?.prefer_url,
    render_variant: options?.render_variant,
  })
    .filter(([, value]) => value !== undefined && value !== false && value !== '')
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join('&')

  const query = search ? `?${search}` : ''
  return `/render-books/jobs/${jobId}/files/${fileKind}${query}`
}

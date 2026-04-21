import type { RequestAdapter, RequestConfig } from '@fba/api-sdk'
import { createFbaApiSdk } from '@fba/api-sdk'
import { http } from '@/http/http'
import { getEnvBaseUrl } from '@/utils'

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

/**
 * 实现适用于 unibest 的网络适配器
 * 将 SDK 的请求底层转接到 unibest 的请求实现
 */
const unibestRequestAdapter: RequestAdapter = {
  request<T = unknown>(config: RequestConfig): Promise<T> {
    return new Promise((resolve, reject) => {
      const payload = sanitizeRequestValue(config.params ?? config.data)

      http<T>({
        url: config.url,
        method: (config.method || 'GET') as any,
        data: payload,
        header: config.headers,
        timeout: config.timeout || 15000,
      }).then((data) => {
        resolve({ code: 200, msg: 'ok', data } as unknown as T)
      }).catch((err) => {
        const status = (err as any)?.statusCode
        const data = (err as any)?.data
        if (status) {
          reject({ response: { status, data } })
          return
        }
        reject(err)
      })
    })
  },
}

/**
 * 实例化 FBA API SDK
 */
export const fbaApi = createFbaApiSdk({
  baseURL: import.meta.env.VITE_API_BASE_URL || getEnvBaseUrl() || 'http://127.0.0.1:8000',
  adapter: unibestRequestAdapter,
  apiPrefix: import.meta.env.VITE_API_PREFIX || '/api/v1',
  getToken: () => getStoredAccessToken(),
})

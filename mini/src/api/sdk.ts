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

/**
 * 实现适用于 unibest 的网络适配器
 * 将 SDK 的请求底层转接到 unibest 的请求实现
 */
const unibestRequestAdapter: RequestAdapter = {
  request<T = unknown>(config: RequestConfig): Promise<T> {
    return new Promise((resolve, reject) => {
      http<T>({
        url: config.url,
        method: (config.method || 'GET') as any,
        data: config.params || config.data,
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

// 兼容旧 SDK 缓存：统一支持 session_id 查询（number）和旧的 question_ids 查询（number[]）
const rawCheckFavorites = fbaApi.qbank.question.checkFavorites.bind(fbaApi.qbank.question)
const rawGetNotes = fbaApi.qbank.question.getNotes.bind(fbaApi.qbank.question)

fbaApi.qbank.question.checkFavorites = ((sessionIdOrQuestionIds: number | number[]) => {
  if (Array.isArray(sessionIdOrQuestionIds)) {
    return rawCheckFavorites(sessionIdOrQuestionIds)
  }
  return fbaApi.qbank.request.get(`/questions/sessions/${sessionIdOrQuestionIds}/favorites`) as Promise<Record<number, boolean>>
}) as typeof fbaApi.qbank.question.checkFavorites

fbaApi.qbank.question.getNotes = ((sessionIdOrQuestionIds: number | number[]) => {
  if (Array.isArray(sessionIdOrQuestionIds)) {
    return rawGetNotes(sessionIdOrQuestionIds)
  }
  return fbaApi.qbank.request.get(`/questions/sessions/${sessionIdOrQuestionIds}/notes`) as Promise<Record<number, any>>
}) as typeof fbaApi.qbank.question.getNotes

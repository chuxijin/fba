import type { CustomRequestOptions, IResponse } from '@/http/types'
import { useTokenStore } from '@/store/token'
import { isDoubleTokenMode } from '@/utils'
import { applyRefreshCookieHeader, hasStoredRefreshCookie, syncRefreshCookieFromResponse } from '@/utils/auth-cookie'
import { toLoginPage } from '@/utils/toLoginPage'
import { ResultEnum } from './tools/enum'

// 刷新 token 状态管理
let refreshing = false // 防止重复刷新 token 标识
let taskQueue: Array<{
  options: CustomRequestOptions
  resolve: (value: any) => void
  reject: (reason?: any) => void
}> = [] // 刷新 token 请求队列
let handlingAuthFailure = false // 防止重复登出/跳转/提示

function isRefreshRequest(url?: string) {
  return typeof url === 'string' && url.includes('/auth/refresh')
}

function extractErrorMessage(error: any): string {
  return String(
    error?.msg
    || error?.message
    || error?.data?.msg
    || error?.data?.message
    || '',
  ).trim()
}

function getAuthFailureToast(error?: any): string {
  const rawMessage = extractErrorMessage(error)
  if (rawMessage.includes('异地登录')) {
    return '账号已在其他设备登录，请重新登录'
  }
  return '登录已过期，请重新登录'
}

async function handleAuthFailure(error?: any) {
  if (handlingAuthFailure) {
    return
  }

  handlingAuthFailure = true
  const tokenStore = useTokenStore()
  try {
    await tokenStore.logout()
  }
  finally {
    uni.showToast({
      title: getAuthFailureToast(error),
      icon: 'none',
    })
    toLoginPage()
    setTimeout(() => {
      handlingAuthFailure = false
    }, 1200)
  }
}

export function http<T>(options: CustomRequestOptions) {
  // 1. 返回 Promise 对象
  return new Promise<T>((resolve, reject) => {
    uni.request({
      ...options,
      header: applyRefreshCookieHeader(options.header),
      dataType: 'json',
      // #ifndef MP-WEIXIN
      responseType: 'json',
      // #endif
      // 响应成功
      success: async (res) => {
        syncRefreshCookieFromResponse(res)
        const responseData = res.data as IResponse<T>
        const { code } = responseData

        // 检查是否是401错误（包括HTTP状态码401或业务码401）
        const isTokenExpired = res.statusCode === 401 || code === 401

        if (isTokenExpired) {
          const tokenStore = useTokenStore()
          if (!isDoubleTokenMode) {
            // 未启用双token策略，清理用户信息，跳转到登录页
            await handleAuthFailure(responseData)
            return reject(res)
          }

          if (isRefreshRequest(options.url)) {
            await handleAuthFailure(responseData)
            return reject(res)
          }

          /* -------- 无感刷新 token ----------- */
          // token 失效的，且有刷新 token cookie 的，才放到请求队列里
          if (hasStoredRefreshCookie()) {
            taskQueue.push({
              options,
              resolve,
              reject,
            })
          }

          // 如果有 refreshToken 且未在刷新中，发起刷新 token 请求
          if (hasStoredRefreshCookie() && !refreshing) {
            refreshing = true
            try {
              // 发起刷新 token 请求（使用 store 的 refreshToken 方法）
              await tokenStore.refreshToken()
              // 刷新 token 成功
              refreshing = false
              // 将任务队列的所有任务重新请求
              const pendingQueue = [...taskQueue]
              taskQueue = []
              pendingQueue.forEach((task) => {
                task.resolve(http<T>(task.options))
              })
            }
            catch (refreshErr) {
              console.error('刷新 token 失败:', refreshErr)
              refreshing = false
              const pendingQueue = [...taskQueue]
              taskQueue = []
              pendingQueue.forEach(task => task.reject(refreshErr))
              await handleAuthFailure(refreshErr)
            }
          }

          if (hasStoredRefreshCookie()) {
            return
          }

          return reject(res)
        }

        // 处理其他成功状态（HTTP状态码200-299）
        if (res.statusCode >= 200 && res.statusCode < 300) {
          // 处理业务逻辑错误
          if (code !== ResultEnum.Success0 && code !== ResultEnum.Success200) {
            uni.showToast({
              icon: 'none',
              title: responseData.msg || responseData.message || '请求错误',
            })
            return reject(responseData.data)
          }
          return resolve(responseData.data)
        }

        // 处理其他错误
        const isAuthError = res.statusCode === 401 || res.statusCode === 403
        if (isAuthError && isRefreshRequest(options.url)) {
          return reject(res)
        }

        !options.hideErrorToast
        && uni.showToast({
          icon: 'none',
          title: (res.data as any).msg || '请求错误',
        })
        reject(res)
      },
      // 响应失败
      fail(err) {
        if (!options.hideErrorToast) {
          uni.showToast({
            icon: 'none',
            title: '网络错误，换个网络试试',
          })
        }
        reject(err)
      },
    })
  })
}

/**
 * GET 请求
 * @param url 后台地址
 * @param query 请求query参数
 * @param header 请求头，默认为json格式
 * @returns
 */
export function httpGet<T>(url: string, query?: Record<string, any>, header?: Record<string, any>, options?: Partial<CustomRequestOptions>) {
  return http<T>({
    url,
    query,
    method: 'GET',
    header,
    ...options,
  })
}

/**
 * POST 请求
 * @param url 后台地址
 * @param data 请求body参数
 * @param query 请求query参数，post请求也支持query，很多微信接口都需要
 * @param header 请求头，默认为json格式
 * @returns
 */
export function httpPost<T>(url: string, data?: Record<string, any>, query?: Record<string, any>, header?: Record<string, any>, options?: Partial<CustomRequestOptions>) {
  return http<T>({
    url,
    query,
    data,
    method: 'POST',
    header,
    ...options,
  })
}
/**
 * PUT 请求
 */
export function httpPut<T>(url: string, data?: Record<string, any>, query?: Record<string, any>, header?: Record<string, any>, options?: Partial<CustomRequestOptions>) {
  return http<T>({
    url,
    data,
    query,
    method: 'PUT',
    header,
    ...options,
  })
}

/**
 * DELETE 请求（无请求体，仅 query）
 */
export function httpDelete<T>(url: string, query?: Record<string, any>, header?: Record<string, any>, options?: Partial<CustomRequestOptions>) {
  return http<T>({
    url,
    query,
    method: 'DELETE',
    header,
    ...options,
  })
}

// 支持与 axios 类似的API调用
http.get = httpGet
http.post = httpPost
http.put = httpPut
http.delete = httpDelete

// 支持与 alovaJS 类似的API调用
http.Get = httpGet
http.Post = httpPost
http.Put = httpPut
http.Delete = httpDelete

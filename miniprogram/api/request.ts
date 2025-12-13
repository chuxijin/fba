/**
 * 网络请求封装
 * 基于 uni.request 的二次封装
 */

import type { ApiResponse, RequestConfig } from './types'

/** 请求配置 */
const config = {
  /** 基础 URL（从环境变量读取） */
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',

  /** API 版本前缀（从环境变量读取） */
  apiPrefix: import.meta.env.VITE_API_PREFIX || '/api/v1',

  /** 请求超时时间（毫秒，从环境变量读取） */
  timeout: Number(import.meta.env.VITE_API_TIMEOUT) || 10000,

  /** Token 存储的 key（与 LoginModal 和 stores/user.ts 保持一致） */
  tokenKey: 'access_token',

  /** 成功响应码 */
  successCode: 200,
}

/**
 * 获取 Token
 */
function getToken(): string {
  try {
    return uni.getStorageSync(config.tokenKey) || ''
  } catch (error) {
    console.error('[Request] 获取 Token 失败:', error)
    return ''
  }
}

/**
 * 设置 Token
 */
export function setToken(token: string): void {
  try {
    uni.setStorageSync(config.tokenKey, token)
  } catch (error) {
    console.error('[Request] 设置 Token 失败:', error)
  }
}

/**
 * 清除 Token
 */
export function clearToken(): void {
  try {
    uni.removeStorageSync(config.tokenKey)
  } catch (error) {
    console.error('[Request] 清除 Token 失败:', error)
  }
}

/**
 * 显示 Loading
 */
function showLoading(text = '加载中...') {
  uni.showLoading({
    title: text,
    mask: true,
  })
}

/**
 * 隐藏 Loading
 */
function hideLoading() {
  uni.hideLoading()
}

/**
 * 显示错误提示
 */
function showError(message: string) {
  uni.showToast({
    title: message,
    icon: 'none',
    duration: 2000,
  })
}

/**
 * 处理 URL 参数
 */
function buildURL(url: string, params?: Record<string, any>): string {
  if (!params || Object.keys(params).length === 0) {
    return url
  }

  const query = Object.keys(params)
    .filter((key) => params[key] !== undefined && params[key] !== null)
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`)
    .join('&')

  return query ? `${url}?${query}` : url
}

/**
 * 统一请求方法
 */
function request<T = any>(options: RequestConfig): Promise<T> {
  const {
    url,
    method = 'GET',
    data,
    params,
    header = {},
    timeout = config.timeout,
    needToken = true,
    showLoading: enableLoading = false,
    loadingText = '加载中...',
  } = options

  // 显示 Loading
  if (enableLoading) {
    showLoading(loadingText)
  }

  // 构建完整 URL（自动添加 API 前缀）
  const fullURL = buildURL(`${config.baseURL}${config.apiPrefix}${url}`, params)

  // 构建请求头
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...header,
  }

  // 添加 Token
  if (needToken) {
    const token = getToken()
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }
  }

  return new Promise<T>((resolve, reject) => {
    uni.request({
      url: fullURL,
      method,
      data,
      header: headers,
      timeout,
      success: (res) => {
        // 隐藏 Loading
        if (enableLoading) {
          hideLoading()
        }

        // 检查 HTTP 状态码
        if (res.statusCode !== 200) {
          const errorMsg = `请求失败: ${res.statusCode}`
          showError(errorMsg)
          reject(new Error(errorMsg))
          return
        }

        // 检查业务状态码
        const response = res.data as ApiResponse<T>

        if (response.code === config.successCode) {
          // 请求成功，返回数据
          resolve(response.data)
        } else {
          // 业务错误处理
          handleBusinessError(response.code, response.msg)
          reject(new Error(response.msg))
        }
      },
      fail: (error) => {
        // 隐藏 Loading
        if (enableLoading) {
          hideLoading()
        }

        // 网络错误处理
        handleNetworkError(error)
        reject(error)
      },
    })
  })
}

/**
 * 处理业务错误
 */
function handleBusinessError(code: number, message: string) {
  switch (code) {
    case 401:
      // Token 过期或无效
      console.warn('[Request] Token 过期或无效')
      showError('登录已过期，请重新登录')
      clearToken()
      // 跳转到登录页（延迟执行，避免阻塞）
      setTimeout(() => {
        // 只在非登录页时跳转
        const pages = getCurrentPages()
        const currentPage = pages[pages.length - 1]
        if (currentPage && currentPage.route !== 'pages/login/index') {
          console.log('[Request] 跳转到登录页')
        }
      }, 1500)
      break

    case 403:
      console.warn('[Request] 权限不足:', message)
      showError('暂无权限访问')
      break

    case 404:
      console.warn('[Request] 资源不存在:', message)
      showError('请求的资源不存在')
      break

    case 500:
      console.error('[Request] 服务器错误:', message)
      showError('服务器错误，请稍后重试')
      break

    default:
      console.warn('[Request] 业务错误:', code, message)
      showError(message || '请求失败')
      break
  }
}

/**
 * 处理网络错误
 */
function handleNetworkError(error: any) {
  console.error('[Request] 网络请求失败:', error)

  if (error.errMsg) {
    if (error.errMsg.includes('timeout')) {
      showError('请求超时，请检查网络连接')
    } else if (error.errMsg.includes('fail')) {
      showError('网络连接失败，请检查网络设置')
    } else {
      showError('网络异常，请稍后重试')
    }
  } else {
    showError('网络异常，请稍后重试')
  }
}

/**
 * GET 请求
 */
export function get<T = any>(
  url: string,
  params?: Record<string, any>,
  options?: Omit<RequestConfig, 'url' | 'method' | 'params'>
): Promise<T> {
  return request<T>({
    url,
    method: 'GET',
    params,
    ...options,
  })
}

/**
 * POST 请求
 */
export function post<T = any>(
  url: string,
  data?: any,
  options?: Omit<RequestConfig, 'url' | 'method' | 'data'>
): Promise<T> {
  return request<T>({
    url,
    method: 'POST',
    data,
    ...options,
  })
}

/**
 * PUT 请求
 */
export function put<T = any>(
  url: string,
  data?: any,
  options?: Omit<RequestConfig, 'url' | 'method' | 'data'>
): Promise<T> {
  return request<T>({
    url,
    method: 'PUT',
    data,
    ...options,
  })
}

/**
 * DELETE 请求
 */
export function del<T = any>(
  url: string,
  params?: Record<string, any>,
  options?: Omit<RequestConfig, 'url' | 'method' | 'params'>
): Promise<T> {
  return request<T>({
    url,
    method: 'DELETE',
    params,
    ...options,
  })
}

/**
 * PATCH 请求
 */
export function patch<T = any>(
  url: string,
  data?: any,
  options?: Omit<RequestConfig, 'url' | 'method' | 'data'>
): Promise<T> {
  return request<T>({
    url,
    method: 'PATCH',
    data,
    ...options,
  })
}

/** 导出请求方法 */
export default {
  get,
  post,
  put,
  delete: del,
  patch,
  setToken,
  clearToken,
}

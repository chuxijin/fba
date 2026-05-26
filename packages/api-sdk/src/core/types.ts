import type { AxiosInstance, AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios'
import type { ApiError } from './errors'

/**
 * 请求生命周期钩子, 用于注入日志 / metrics / observability
 *
 * 所有钩子都可以是 async, SDK 会 await; 异常会被 catch 并打到 console.error 但不会中断主流程
 */
export interface RequestHooks {
  /** 请求发出前 (token 已注入, 重试前每次都会触发) */
  onRequest?: (ctx: HookRequestCtx) => void | Promise<void>
  /** 响应到达后, 业务拆包前 (即使 code !== 200 也会触发) */
  onResponse?: (ctx: HookResponseCtx) => void | Promise<void>
  /** 错误最终抛给调用方前 (重试结束后才触发) */
  onError?: (ctx: HookErrorCtx) => void | Promise<void>
}

export interface HookRequestCtx {
  url: string
  method: string
  config: InternalAxiosRequestConfig
  attempt: number
}

export interface HookResponseCtx {
  url: string
  method: string
  status: number
  data: unknown
  durationMs: number
  config: InternalAxiosRequestConfig
  attempt: number
}

export interface HookErrorCtx {
  url: string
  method: string
  error: Error
  config?: InternalAxiosRequestConfig
  attempt: number
}

export interface RetryOptions {
  /** 重试次数 (不含首次), 默认 0 (关闭) */
  count: number
  /** 基础延迟 (ms), 默认 300 */
  baseDelayMs?: number
  /** 最大延迟 (ms), 默认 5000 */
  maxDelayMs?: number
  /** 哪些 HTTP 状态码触发重试, 默认 [502, 503, 504] */
  statusCodes?: number[]
  /** 是否对网络错误 (无 response) 重试, 默认 true */
  retryOnNetworkError?: boolean
}

/**
 * Plugin: 横切关注点的模块化封装 (sentry / 日志 / metrics 等)
 *
 * 多个 plugin 的同名钩子会按数组顺序依次执行, 后者不阻塞前者;
 * 任意 plugin 的钩子异常会被 catch + console.error, 不影响主流程
 *
 * 实际上是把 RequestHooks 装进可复用的盒子, 让一个文件 = 一个关注点
 */
export interface SdkPlugin {
  /** 仅用于日志/调试 */
  name?: string
  /** 该 plugin 注入的钩子 */
  hooks?: RequestHooks
}

export interface SetupSdkOptions {
  baseURL: string

  /** 可选 axios adapter; 小程序传 wx-request 风格 adapter, Node 用 http adapter, 浏览器不传 */
  adapter?: AxiosRequestConfig['adapter']

  /** 鉴权 token 获取, 每次请求时调用; 可异步 */
  getToken?: () => string | undefined | null | Promise<string | undefined | null>

  /**
   * Token 自然过期回调; 仅在响应 msg 为 "Token 已过期" 时触发
   *
   * 并发安全: SDK 内部会对同一时刻的多个 401 dedupe, 只调用一次 onTokenExpired,
   * 所有并发请求等待同一个 promise, 成功后统一重放
   *
   * 返回 true → SDK 自动重放原请求; 返回 false / 抛错 → 走 onUnauthorized
   */
  onTokenExpired?: () => Promise<boolean>

  /** 401 兜底回调 (refresh 失败 / refresh 不可用 / 不可恢复的 401), 通常用于跳登录页 */
  onUnauthorized?: () => void | Promise<void>

  /** 业务错误回调 (code !== 200, 不含 401) */
  onError?: (error: ApiError) => void

  /** 请求超时 ms, 默认 30000 */
  timeout?: number

  /** 每次请求合并的额外 headers, 可异步 */
  extraHeaders?: () => Record<string, string> | Promise<Record<string, string>>

  /** 重试配置 (默认关闭) */
  retry?: RetryOptions

  /** 直接配置的钩子; 与 plugins 一起按 [hooks, ...plugins] 顺序执行 */
  hooks?: RequestHooks

  /** Plugin 列表; 横切关注点的模块化封装 */
  plugins?: SdkPlugin[]

  /**
   * 公开接口路径白名单 (子串匹配): 命中后跳过 Authorization 注入
   *
   * 例: ['/auth/captcha', '/auth/login', '/auth/refresh']
   * 比 mini adapter 事后删 header 更前置, 避免 hey-api generated client 一开始就注入旧 token
   */
  skipAuthPaths?: string[]
}

/** createSdk 返回的实例, 多实例隔离场景使用 */
export interface SdkInstance {
  /** axios 实例; 也可注入到 hey-api generated client */
  axios: AxiosInstance
  /** 当前配置的副本 */
  options: SetupSdkOptions
  /** 关闭并释放资源 (清空 refresh dedupe 状态等), 调用后实例不再可用 */
  dispose: () => void
}

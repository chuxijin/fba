import axios, { type AxiosError, type AxiosInstance, type AxiosResponse, type AxiosStatic, type InternalAxiosRequestConfig } from 'axios'
import { ApiError, CanceledError, NetworkError, TimeoutError, UnauthorizedError } from './errors'
import type { HookRequestCtx, RetryOptions, SdkInstance, SetupSdkOptions } from './types'

const TOKEN_EXPIRED_MSG = 'Token 已过期'
const DEFAULT_TIMEOUT_MS = 30_000
const DEFAULT_RETRY_STATUS_CODES = [502, 503, 504]
const DEFAULT_RETRY_BASE_DELAY_MS = 300
const DEFAULT_RETRY_MAX_DELAY_MS = 5000

/** 每个 SDK 实例的内部状态; createSdk 之间互相隔离 */
interface InstanceState {
  refreshing: Promise<boolean> | null
  /**
   * unauthorized 单飞标记: 同一次"全局未登录"事件只回调 onUnauthorized 一次
   *
   * 并发 N 个 401 → refresh 失败 → 不重复触发 N 次 toast / N 次跳登录
   * 任意一次成功的 refresh 都会把它清零, 让真正的下次未登录还能被识别
   */
  unauthorizedFired: boolean
}

interface AxiosConfigWithMeta extends InternalAxiosRequestConfig {
  _retry?: boolean
  _attempt?: number
  _startedAt?: number
}

function isCanceled(error: unknown): boolean {
  if (!error || typeof error !== 'object') {
    return false
  }
  const err = error as { name?: string, code?: string, message?: string }
  if (err.name === 'CanceledError' || err.name === 'AbortError') {
    return true
  }
  if (err.code === 'ERR_CANCELED') {
    return true
  }
  return axios.isCancel?.(error) === true
}

function isTimeout(error: unknown): boolean {
  if (!error || typeof error !== 'object') {
    return false
  }
  const err = error as { code?: string, message?: string }
  return err.code === 'ECONNABORTED' || /timeout/i.test(err.message ?? '')
}

function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function computeBackoff(attempt: number, opts: Required<Pick<RetryOptions, 'baseDelayMs' | 'maxDelayMs'>>): number {
  const exp = opts.baseDelayMs * 2 ** Math.max(0, attempt - 1)
  return Math.min(opts.maxDelayMs, exp)
}

async function runHook<T>(hook: ((ctx: T) => void | Promise<void>) | undefined, ctx: T): Promise<void> {
  if (!hook) {
    return
  }
  try {
    await hook(ctx)
  }
  catch (hookError) {
    // 钩子异常不应该影响主请求流程
    console.error('[sdk] hook error', hookError)
  }
}

/**
 * 把 options.hooks 与 options.plugins[].hooks 合并成一组扁平钩子
 *
 * 多个 plugin 的同名钩子按 [options.hooks, ...plugins] 顺序串行执行;
 * 任意一个的异常都不影响后续 (runHook 内已 catch)
 *
 * :param opts: SDK 配置
 */
function buildHooks(opts: SetupSdkOptions): import('./types').RequestHooks {
  const sources: import('./types').RequestHooks[] = []
  if (opts.hooks) {
    sources.push(opts.hooks)
  }
  if (opts.plugins?.length) {
    for (const plugin of opts.plugins) {
      if (plugin.hooks) {
        sources.push(plugin.hooks)
      }
    }
  }

  if (sources.length === 0) {
    return {}
  }

  return {
    async onRequest(ctx) {
      for (const src of sources) {
        await runHook(src.onRequest, ctx)
      }
    },
    async onResponse(ctx) {
      for (const src of sources) {
        await runHook(src.onResponse, ctx)
      }
    },
    async onError(ctx) {
      for (const src of sources) {
        await runHook(src.onError, ctx)
      }
    },
  }
}

function buildErrorFromAxios(error: AxiosError, url: string): Error {
  if (isCanceled(error)) {
    return new CanceledError()
  }

  if (isTimeout(error)) {
    return new TimeoutError(`Request timed out: ${url}`, error)
  }

  const response = error.response
  if (!response) {
    return new NetworkError(error.message || `Network request failed: ${url}`, error)
  }

  const body = response.data as { code?: number, msg?: string, data?: unknown } | undefined
  const code = body?.code ?? response.status
  const msg = body?.msg ?? error.message ?? String(response.status)

  if (response.status === 401 || code === 401) {
    return new UnauthorizedError({ msg, status: response.status, data: body?.data })
  }

  return new ApiError({ code, msg, status: response.status, data: body?.data })
}

/**
 * 同一时刻只允许一个 refresh 在飞; 并发调用者等同一个 promise
 *
 * :param state: 当前 SDK 实例的内部状态
 * :param opts: SDK 配置
 */
async function dedupedRefresh(state: InstanceState, opts: SetupSdkOptions): Promise<boolean> {
  if (state.refreshing) {
    return state.refreshing
  }
  if (!opts.onTokenExpired) {
    return false
  }
  state.refreshing = (async () => {
    try {
      const ok = await opts.onTokenExpired!()
      if (ok) {
        // refresh 成功 → 重置 unauthorized 单飞标记, 让下一次真正的未登录还能被识别
        state.unauthorizedFired = false
      }
      return ok
    }
    catch {
      return false
    }
    finally {
      state.refreshing = null
    }
  })()
  return state.refreshing
}

/**
 * unauthorized 单飞: 同一次未登录事件只回调一次 opts.onUnauthorized
 *
 * 5 个并发请求 401 → refresh 失败 → 只触发一次 toast / 一次跳登录
 * refresh 成功时 dedupedRefresh 会清零 unauthorizedFired, 下次真未登录仍能识别
 *
 * :param state: 当前 SDK 实例的内部状态
 * :param opts: SDK 配置
 */
async function fireUnauthorizedOnce(state: InstanceState, opts: SetupSdkOptions): Promise<void> {
  if (state.unauthorizedFired) {
    return
  }
  state.unauthorizedFired = true
  try {
    await opts.onUnauthorized?.()
  }
  catch (err) {
    console.error('[sdk] onUnauthorized handler error', err)
  }
}

/**
 * 判断 url 是否命中公开接口白名单 (子串匹配)
 *
 * :param url: 请求 url, 可能含 baseURL / query
 * :param paths: 白名单子串数组
 */
function matchSkipAuthPath(url: string, paths: string[] | undefined): boolean {
  if (!paths || paths.length === 0) {
    return false
  }
  return paths.some(path => url.includes(path))
}

interface Handle401Args {
  instance: AxiosInstance
  state: InstanceState
  opts: SetupSdkOptions
  config: AxiosConfigWithMeta | undefined
  msg: string | undefined
  status: number | undefined
  data: unknown
}

type Handle401Result = { replayed: true, value: AxiosResponse } | { replayed: false }

async function handle401(args: Handle401Args): Promise<Handle401Result> {
  const { instance, state, opts, config, msg } = args

  if (!config) {
    await fireUnauthorizedOnce(state, opts)
    return { replayed: false }
  }

  if (config._retry) {
    // 已经重放过一次, 还是 401 → 不再尝试 refresh, 让外层处理
    await fireUnauthorizedOnce(state, opts)
    return { replayed: false }
  }

  if (msg === TOKEN_EXPIRED_MSG && opts.onTokenExpired) {
    config._retry = true
    const refreshed = await dedupedRefresh(state, opts)
    if (refreshed) {
      try {
        const value = await instance.request(config)
        return { replayed: true, value }
      }
      catch {
        // 重放失败, 落到下方 fireUnauthorizedOnce 兜底
      }
    }
  }

  await fireUnauthorizedOnce(state, opts)
  return { replayed: false }
}

interface ShouldRetryArgs {
  retry: RetryOptions | undefined
  attempt: number
  status?: number
  isNetwork: boolean
}

function shouldRetry(args: ShouldRetryArgs): boolean {
  const { retry, attempt, status, isNetwork } = args
  if (!retry || retry.count <= 0 || attempt > retry.count) {
    return false
  }
  if (status !== undefined) {
    const codes = retry.statusCodes ?? DEFAULT_RETRY_STATUS_CODES
    return codes.includes(status)
  }
  if (isNetwork) {
    return retry.retryOnNetworkError !== false
  }
  return false
}

/** 内部创建 SDK 实例的通用工厂, 不绑定模块级状态 */
function buildInstance(opts: SetupSdkOptions): SdkInstance {
  const state: InstanceState = { refreshing: null, unauthorizedFired: false }
  const hooks = buildHooks(opts)

  const instance = axios.create({
    baseURL: opts.baseURL,
    adapter: opts.adapter,
    timeout: opts.timeout ?? DEFAULT_TIMEOUT_MS,
  })

  // ----- 请求拦截器: token 注入 + extraHeaders + hooks.onRequest + 计时 -----
  instance.interceptors.request.use(async (rawConfig) => {
    const config = rawConfig as AxiosConfigWithMeta
    config._attempt = (config._attempt ?? 0) + 1
    config._startedAt = Date.now()

    const headers: Record<string, string> = { ...(config.headers as Record<string, string> | undefined) }

    const fullUrl = `${config.baseURL ?? opts.baseURL ?? ''}${config.url ?? ''}`
    const isSkipAuthPath = matchSkipAuthPath(fullUrl, opts.skipAuthPaths)

    // 调用方可通过显式设置 Authorization: '' 来跳过 token 注入 (refresh / login 接口)
    const hasExplicitAuth = Object.prototype.hasOwnProperty.call(headers, 'Authorization')
    if (hasExplicitAuth && !headers.Authorization) {
      delete headers.Authorization
    }
    else if (isSkipAuthPath) {
      // 白名单路径: 既不注入 token, 也清掉调用方可能误传的 Authorization
      delete headers.Authorization
    }
    else if (!hasExplicitAuth && opts.getToken) {
      const token = await opts.getToken()
      if (token) {
        headers.Authorization = `Bearer ${token}`
      }
    }

    if (opts.extraHeaders) {
      const extras = await opts.extraHeaders()
      if (extras) {
        Object.assign(headers, extras)
      }
    }

    config.headers = headers as typeof config.headers

    const hookCtx: HookRequestCtx = {
      url: config.url ?? '',
      method: (config.method ?? 'GET').toUpperCase(),
      config,
      attempt: config._attempt,
    }
    await runHook(hooks.onRequest, hookCtx)

    return config
  })

  // ----- 响应成功拦截器: 拆 ResponseModel + 401/business 错误统一抛 + hooks -----
  instance.interceptors.response.use(
    async (res) => {
      const config = res.config as AxiosConfigWithMeta
      const body = res.data
      const durationMs = config._startedAt ? Date.now() - config._startedAt : 0

      // 后端业务约定 ResponseModel = { code, msg, data }
      if (body && typeof body === 'object' && 'code' in body) {
        const code = (body as { code: number }).code
        const msg = (body as { msg?: string }).msg
        const data = (body as { data?: unknown }).data

        await runHook(hooks.onResponse, {
          url: config.url ?? '',
          method: (config.method ?? 'GET').toUpperCase(),
          status: res.status,
          data: body,
          durationMs,
          config,
          attempt: config._attempt ?? 1,
        })

        if (code === 401) {
          const result = await handle401({
            instance,
            state,
            opts,
            config,
            msg,
            status: res.status,
            data,
          })
          if (result.replayed) {
            return result.value
          }
          const err = new UnauthorizedError({ msg, status: res.status, data })
          await runHook(hooks.onError, {
            url: config.url ?? '',
            method: (config.method ?? 'GET').toUpperCase(),
            error: err,
            config,
            attempt: config._attempt ?? 1,
          })
          return Promise.reject(err)
        }

        if (code !== 200 && code !== 0) {
          // 业务错误也可能需要重试 (例如 ResponseModel.code 透传 5xx); 这里把请求重新走 retry 决策
          if (shouldRetry({ retry: opts.retry, attempt: config._attempt ?? 1, status: res.status, isNetwork: false })) {
            const retryOpts = opts.retry!
            const wait = computeBackoff(config._attempt ?? 1, {
              baseDelayMs: retryOpts.baseDelayMs ?? DEFAULT_RETRY_BASE_DELAY_MS,
              maxDelayMs: retryOpts.maxDelayMs ?? DEFAULT_RETRY_MAX_DELAY_MS,
            })
            await delay(wait)
            return instance.request(config)
          }

          const err = new ApiError({ code, msg: msg ?? `business error ${code}`, status: res.status, data })
          opts.onError?.(err)
          await runHook(hooks.onError, {
            url: config.url ?? '',
            method: (config.method ?? 'GET').toUpperCase(),
            error: err,
            config,
            attempt: config._attempt ?? 1,
          })
          return Promise.reject(err)
        }

        // 兼容旧调用方式: 把 ResponseModel.data 放到 axios response.data 位置, 业务侧 await xxx() 后读 .data 即可
        return { ...res, data }
      }

      // 非 ResponseModel 包裹的响应直接透传 (比如二进制 / OpenAPI raw 响应)
      await runHook(hooks.onResponse, {
        url: config.url ?? '',
        method: (config.method ?? 'GET').toUpperCase(),
        status: res.status,
        data: body,
        durationMs,
        config,
        attempt: config._attempt ?? 1,
      })

      return res
    },
    async (rawError) => {
      const error = rawError as AxiosError
      const config = (error.config ?? undefined) as AxiosConfigWithMeta | undefined
      const url = config?.url ?? ''
      const method = (config?.method ?? 'GET').toUpperCase()
      const attempt = config?._attempt ?? 1

      // 1) 取消请求直接返回 CanceledError, 不走重试
      if (isCanceled(error)) {
        const err = new CanceledError()
        await runHook(hooks.onError, { url, method, error: err, config, attempt })
        return Promise.reject(err)
      }

      // 2) HTTP 401 (header 层): 走 refresh + 重放
      if (error.response?.status === 401) {
        const responseBody = error.response.data as { code?: number, msg?: string, data?: unknown } | undefined
        const msg = responseBody?.msg
        const result = await handle401({
          instance,
          state,
          opts,
          config,
          msg,
          status: error.response.status,
          data: responseBody?.data,
        })
        if (result.replayed) {
          return result.value
        }
        const err = new UnauthorizedError({ msg, status: 401, data: responseBody?.data })
        await runHook(hooks.onError, { url, method, error: err, config, attempt })
        return Promise.reject(err)
      }

      // 3) 5xx / 网络错误: 看是否要重试
      const status = error.response?.status
      const isNetwork = !error.response
      if (config && shouldRetry({ retry: opts.retry, attempt, status, isNetwork })) {
        const retryOpts = opts.retry!
        const wait = computeBackoff(attempt, {
          baseDelayMs: retryOpts.baseDelayMs ?? DEFAULT_RETRY_BASE_DELAY_MS,
          maxDelayMs: retryOpts.maxDelayMs ?? DEFAULT_RETRY_MAX_DELAY_MS,
        })
        await delay(wait)
        return instance.request(config)
      }

      // 4) 走错误转换 + 钩子
      const transformed = buildErrorFromAxios(error, url)
      await runHook(hooks.onError, { url, method, error: transformed, config, attempt })
      return Promise.reject(transformed)
    },
  )

  return {
    axios: instance,
    options: opts,
    dispose() {
      state.refreshing = null
    },
  }
}

// ===== 多实例 API: createSdk =====
/**
 * 创建一个隔离的 SDK 实例; 不绑定模块级状态, 适合 SSR / 多租户 / 测试场景
 *
 * :param opts: SDK 配置
 */
export function createSdk(opts: SetupSdkOptions): SdkInstance {
  return buildInstance(opts)
}

// ===== 兼容旧 API: 模块级单例 setupSdk / getSdkInstance / createClientConfig =====

let sharedInstance: AxiosInstance | null = null
let pendingBaseURL: string | undefined

/**
 * hey-api 生成的 client.gen.ts 在初始化时调用, 用来拿初始 baseURL
 *
 * setupSdk 调用前 axios 实例尚未就绪, 这里只 forward override
 */
export function createClientConfig<T extends { baseURL?: string }>(override?: T): T {
  const base = { baseURL: pendingBaseURL ?? '' } as T
  return { ...base, ...override }
}

/**
 * 初始化全局 SDK 单例; 必须在调用任何 generated 方法之前执行一次
 *
 * 旧调用方继续可用; 新代码推荐 createSdk(opts) 获得隔离的 instance
 *
 * :param opts: SDK 配置
 */
export async function setupSdk(opts: SetupSdkOptions): Promise<AxiosInstance> {
  pendingBaseURL = opts.baseURL
  const instance = buildInstance(opts)
  sharedInstance = instance.axios

  // 把 axios 实例注入到 hey-api generated client
  const mod = await import('../generated/client.gen')
  mod.client.setConfig({ axios: instance.axios as unknown as AxiosStatic, baseURL: opts.baseURL })

  return instance.axios
}

export function getSdkInstance(): AxiosInstance {
  if (!sharedInstance) {
    throw new Error('SDK not initialized. Call setupSdk() before any API call.')
  }
  return sharedInstance
}

// 类型重导出, 方便外部精细控制
export type { RequestHooks, RetryOptions, SdkInstance, SetupSdkOptions } from './types'

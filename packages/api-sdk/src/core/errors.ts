/**
 * SDK 统一错误体系
 *
 * 后端约定: 所有接口返回 ResponseModel<T> = { code: number; msg: string; data?: T }
 * - code === 200 (或 0)        → 成功, resolve(data)
 * - code !== 200, HTTP 2xx     → 业务错误, 抛 ApiError
 * - HTTP 401 / code === 401    → 认证失败, 抛 UnauthorizedError (extends ApiError)
 * - HTTP 5xx / no response     → 网络错误, 抛 NetworkError
 * - timeout                    → 超时, 抛 TimeoutError (extends NetworkError)
 * - AbortSignal aborted        → 取消, 抛 CanceledError
 *
 * 所有错误都暴露 .name / .message / 业务字段, 可以用 instanceof 或 鸭子类型判断
 */

interface ApiErrorArgs {
  code: number
  msg: string
  status?: number
  data?: unknown
}

/** 业务级错误: 后端 code !== 200 时抛出, 携带 code/msg/status/data */
export class ApiError extends Error {
  readonly code: number
  readonly msg: string
  readonly status?: number
  readonly data?: unknown

  constructor(args: ApiErrorArgs) {
    super(args.msg)
    this.name = 'ApiError'
    this.code = args.code
    this.msg = args.msg
    this.status = args.status
    this.data = args.data
  }
}

/** 认证失败: HTTP 401 或后端 code === 401; refresh 失败兜底也走这里 */
export class UnauthorizedError extends ApiError {
  constructor(args: { msg?: string, status?: number, data?: unknown } = {}) {
    super({
      code: 401,
      msg: args.msg ?? '认证已过期，请重新登录',
      status: args.status ?? 401,
      data: args.data,
    })
    this.name = 'UnauthorizedError'
  }
}

/** 网络层错误: 无 response 的请求失败 (DNS / connection refused / 适配器层异常) */
export class NetworkError extends Error {
  readonly cause: unknown

  constructor(message: string, cause?: unknown) {
    super(message)
    this.name = 'NetworkError'
    this.cause = cause
  }
}

/** 请求超时 */
export class TimeoutError extends NetworkError {
  constructor(message = 'Request timed out', cause?: unknown) {
    super(message, cause)
    this.name = 'TimeoutError'
  }
}

/** 请求被 AbortController 取消 */
export class CanceledError extends Error {
  constructor(message = 'Request canceled') {
    super(message)
    this.name = 'CanceledError'
  }
}

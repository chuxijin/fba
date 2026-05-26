/**
 * Runtime entry: re-export the core SDK so consumers can keep importing from
 *   '@fba/api-sdk/runtime'
 *
 * 新业务代码推荐:
 *   import { createSdk } from '@fba/api-sdk'   // 多实例
 * 旧代码继续支持:
 *   import { setupSdk, getSdkInstance } from '@fba/api-sdk/runtime'  // 单例
 */

export {
  createClientConfig,
  createSdk,
  getSdkInstance,
  setupSdk,
} from '../core/create-sdk'

export {
  ApiError,
  CanceledError,
  NetworkError,
  TimeoutError,
  UnauthorizedError,
} from '../core/errors'

export type {
  HookErrorCtx,
  HookRequestCtx,
  HookResponseCtx,
  RequestHooks,
  RetryOptions,
  SdkInstance,
  SetupSdkOptions,
} from '../core/types'

// 兼容旧名字 (legacy 别名, 业务侧偶尔有人作 type 用)
export type ApiResponseError = Error & {
  code?: number
  msg?: string
  status?: number
  data?: unknown
}

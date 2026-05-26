/**
 * @fba/api-sdk
 *
 * 跨端 SDK 主入口
 * - mini / web 通过 setupSdk 或 createSdk 初始化, 然后 import generated 方法直接调用
 * - 类型可从主入口或 ./generated 子入口按需取
 *
 * 调用形态:
 *   import { setupSdk } from '@fba/api-sdk'   // 或 '@fba/api-sdk/runtime'
 *   import { api } from '@/api/sdk'           // 业务侧封装的 generated 别名
 *
 *   await setupSdk({ baseURL, getToken, onTokenExpired, onUnauthorized, hooks, retry })
 *   const { data } = await api.getBankList({ query: { page: 1 } })
 */

// ===== 核心运行时 =====
export {
  createClientConfig,
  createSdk,
  getSdkInstance,
  setupSdk,
} from './core/create-sdk'

// ===== 错误体系 =====
export {
  ApiError,
  CanceledError,
  NetworkError,
  TimeoutError,
  UnauthorizedError,
} from './core/errors'

// ===== 配置类型 =====
export type {
  HookErrorCtx,
  HookRequestCtx,
  HookResponseCtx,
  RequestHooks,
  RetryOptions,
  SdkInstance,
  SdkPlugin,
  SetupSdkOptions,
} from './core/types'

// ===== 类型对齐工具 (告别 as any) =====
export { typed } from './typed'
export type { UnwrappedApi } from './typed'

// ===== 内置 plugin =====
export { loggerPlugin } from './plugins/logger'
export type { LoggerPluginOptions } from './plugins/logger'

// ===== 业务 schema 类型 (手写) =====
export type * from './types'

// ===== 业务 schema 类型 (hey-api 自动生成) =====
// 注: 部分类型可能与手写 types 重名, 这里不 re-export 避免冲突;
// 调用方按需直接 from '@fba/api-sdk/generated' 取最新生成的类型

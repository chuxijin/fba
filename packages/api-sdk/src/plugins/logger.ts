/**
 * 内置 logger plugin: 开箱即用的请求 / 响应 / 错误日志
 *
 * 用法:
 *   ```ts
 *   import { setupSdk, loggerPlugin } from '@fba/api-sdk'
 *
 *   await setupSdk({
 *     baseURL,
 *     plugins: [loggerPlugin({ level: 'verbose' })],
 *   })
 *   ```
 *
 * 默认 (level: 'minimal') 只打:
 *   - 错误 (任意 onError)
 *   - 重试 (attempt > 1)
 * verbose 模式额外打:
 *   - 每个请求 (→ METHOD URL)
 *   - 每个响应 (← METHOD URL STATUS DURATION)
 */

import type { SdkPlugin } from '../core/types'

export interface LoggerPluginOptions {
  /**
   * minimal: 仅打错误和重试; verbose: 打全部请求/响应/错误
   *
   * 默认 minimal (生产推荐); verbose 适合开发调试
   */
  level?: 'minimal' | 'verbose'
  /**
   * 自定义底层 logger; 默认走 console
   *
   * 业务侧可以注入自己的 logger 把 SDK 日志接到统一日志系统
   */
  logger?: (level: 'log' | 'warn' | 'error', message: string, extra?: unknown) => void
  /** 是否打印请求 URL 的 query, 默认 false (避免泄漏敏感参数) */
  includeQuery?: boolean
}

function maskUrl(url: string, includeQuery: boolean): string {
  if (includeQuery) {
    return url
  }
  const i = url.indexOf('?')
  return i === -1 ? url : url.slice(0, i)
}

export function loggerPlugin(opts: LoggerPluginOptions = {}): SdkPlugin {
  const level = opts.level ?? 'minimal'
  const log = opts.logger ?? ((lv, msg, extra) => {
    if (extra !== undefined) {
      console[lv](msg, extra)
    }
    else {
      console[lv](msg)
    }
  })
  const includeQuery = opts.includeQuery ?? false

  return {
    name: 'logger',
    hooks: {
      onRequest: ({ url, method, attempt }) => {
        if (attempt > 1) {
          log('warn', `[SDK] ↻ ${method} ${maskUrl(url, includeQuery)} (retry attempt ${attempt})`)
        }
        else if (level === 'verbose') {
          log('log', `[SDK] → ${method} ${maskUrl(url, includeQuery)}`)
        }
      },
      onResponse: ({ url, method, status, durationMs }) => {
        if (level === 'verbose') {
          log('log', `[SDK] ← ${method} ${maskUrl(url, includeQuery)} ${status} (${durationMs}ms)`)
        }
      },
      onError: ({ url, method, error }) => {
        const err = error as Error & { code?: number, status?: number }
        const codeInfo = err.code !== undefined ? ` code=${err.code}` : ''
        const statusInfo = err.status !== undefined ? ` status=${err.status}` : ''
        log('error', `[SDK] ✗ ${method} ${maskUrl(url, includeQuery)}${codeInfo}${statusInfo}: ${error.message}`)
      },
    },
  }
}

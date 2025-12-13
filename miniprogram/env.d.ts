declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, any>
  export default component
}

/// <reference types="vite/client" />

/**
 * 环境变量类型定义
 *
 * 为 import.meta.env 提供类型支持和 IDE 自动补全
 */
interface ImportMetaEnv {
  /** API 基础地址 */
  readonly VITE_API_BASE_URL: string

  /** API 版本前缀 */
  readonly VITE_API_PREFIX: string

  /** 请求超时时间（毫秒） */
  readonly VITE_API_TIMEOUT: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

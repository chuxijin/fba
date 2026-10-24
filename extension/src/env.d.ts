/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

declare module '*.css?inline' {
  const content: string
  export default content
}

/**
 * 构建期注入的后端基址（见 build.js --api=...）。
 * 未注入时回落到本地开发地址。
 */
declare const __API_BASE__: string | undefined

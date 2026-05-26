# @fba/api-sdk

FBA 后端多端统一 API SDK，供 Web (`youanshang`) 与小程序 (`mini`) 共用。

## 核心特性

- **类型完整 + 自动对齐**：从后端 OpenAPI 自动生成 630+ operations / 802+ schemas；`typed()` 工具把 `ResponseSchemaModel<T>` 自动 unwrap 成 T，业务侧告别 `as any`
- **跨端运行**：浏览器 / Nuxt SSR / 微信小程序 通过可注入 `adapter` 复用同一份代码
- **统一拦截**：自动注入 Bearer Token、统一拆 `ResponseModel = { code, msg, data }`、统一抛 `ApiError`
- **Refresh dedupe**：并发 401 自动合并为单次 refresh，防止 N 个请求同时刷 token 把 session 刷坏
- **Plugin 系统**：横切关注点 (sentry / 日志 / metrics) 模块化封装，多个 plugin 可组合
- **内置 loggerPlugin**：开箱即用的请求/响应/错误日志，可注入自定义 logger 接入统一日志系统
- **重试机制**：5xx / 网络错误 / 业务 code 5xx 按指数退避自动重试（默认关闭，按需开启）
- **请求取消**：原生支持 `AbortSignal`，组件卸载时立即终止飞行请求
- **多实例**：`createSdk(opts)` 返回隔离实例，SSR / 多租户 / 测试零干扰

## 快速开始

### 浏览器 / Nuxt

```ts
import * as g from '@fba/api-sdk/generated'
import { setupSdk, typed, loggerPlugin } from '@fba/api-sdk'

await setupSdk({
  baseURL: 'https://api.example.com',
  getToken: () => localStorage.getItem('access_token') ?? undefined,
  onTokenExpired: async () => {
    // 用 refresh token 续期, 返回 true 让 SDK 自动重放原请求
    return await authStore.refresh()
  },
  onUnauthorized: () => {
    // refresh 失败兜底, 跳登录
    router.push('/login')
  },
  // 可观测性: 错误自动打日志
  plugins: [loggerPlugin({ level: 'verbose' })],
})

// typed() 把响应类型自动 unwrap, 业务侧 .data 直接是 T (不是 ResponseSchemaModel<T>)
export const api = typed(g)

const { data } = await api.getBankList({ query: { page: 1, size: 20 } })
//      ^? GetBankList (内层数据, 不是 ResponseSchemaModel)
```

### 小程序

```ts
import { setupSdk } from '@fba/api-sdk/runtime'

await setupSdk({
  baseURL: 'https://api.example.com',
  // 适配 uni.request / wx.request
  adapter: (config) => new Promise((resolve, reject) => {
    uni.request({
      url: `${config.baseURL || ''}${config.url || ''}`,
      method: config.method as any,
      data: config.data,
      header: config.headers,
      timeout: config.timeout,
      success: (res) => resolve({
        data: res.data,
        status: res.statusCode,
        statusText: String(res.statusCode),
        headers: res.header,
        config,
      }),
      fail: reject,
    })
  }),
  getToken: () => uni.getStorageSync('access_token') || undefined,
})
```

### 多实例 (SSR / 测试 / 多租户)

```ts
import { createSdk } from '@fba/api-sdk'

const sdkA = createSdk({ baseURL: 'https://a.example.com', /* ... */ })
const sdkB = createSdk({ baseURL: 'https://b.example.com', /* ... */ })

// 实例间完全隔离 (refresh 状态、配置、axios 实例)
sdkA.dispose()
sdkB.dispose()
```

## 进阶配置

### 自动重试

```ts
await setupSdk({
  baseURL,
  retry: {
    count: 3,                     // 重试次数 (不含首次)
    baseDelayMs: 300,             // 基础延迟
    maxDelayMs: 5000,             // 最大延迟 (指数退避封顶)
    statusCodes: [502, 503, 504], // 哪些 HTTP 状态触发重试
    retryOnNetworkError: true,    // 无 response 时也重试 (DNS / 断网)
  },
})
```

### 可观测性钩子

```ts
await setupSdk({
  baseURL,
  hooks: {
    onRequest: (ctx) => {
      console.log(`[REQ] ${ctx.method} ${ctx.url} (attempt ${ctx.attempt})`)
    },
    onResponse: (ctx) => {
      metrics.histogram('api.duration_ms', ctx.durationMs, {
        method: ctx.method,
        status: ctx.status,
      })
    },
    onError: (ctx) => {
      Sentry.captureException(ctx.error, { extra: { url: ctx.url } })
    },
  },
})
```

### 取消请求

```ts
const ac = new AbortController()
const promise = api.getBankList({ query: {}, signal: ac.signal })
// 用户切换路由
ac.abort()
// promise 会 reject 一个 CanceledError
```

## 错误体系

```ts
import { ApiError, UnauthorizedError, NetworkError, TimeoutError, CanceledError } from '@fba/api-sdk'

try {
  const { data } = await api.getBankList({})
} catch (err) {
  if (err instanceof UnauthorizedError) {
    // 401, refresh 也救不回来; 已经触发 onUnauthorized
  } else if (err instanceof ApiError) {
    // 业务错误, err.code / err.msg / err.status / err.data 都有
  } else if (err instanceof TimeoutError) {
    // 请求超时
  } else if (err instanceof NetworkError) {
    // DNS / 断网 / adapter 异常, err.cause 是原始错误
  } else if (err instanceof CanceledError) {
    // 调用方主动 abort
  }
}
```

> 说明：业务侧也可以鸭子类型判断 `err.code` / `err.status` / `err.msg`，所有错误都暴露这几个字段。

## 子入口

| 入口 | 用途 |
|---|---|
| `@fba/api-sdk` | 主入口: `setupSdk` / `createSdk` / `typed` / `loggerPlugin` / 错误类 / 业务 schema 类型 |
| `@fba/api-sdk/runtime` | 仅 runtime: `setupSdk` / `createSdk` / `createClientConfig` (hey-api 用) |
| `@fba/api-sdk/generated` | hey-api 自动生成的所有 API 方法 + 类型 |
| `@fba/api-sdk/plugins` | 内置 plugins: `loggerPlugin` |
| `@fba/api-sdk/typed` | 类型对齐: `typed()` + `UnwrappedApi<T>` |

## 类型同步

后端改 schema / 路由后，在 `packages/api-sdk` 跑：

```bash
pnpm gen
```

会重新 dump OpenAPI → 生成 SDK → build dist。详见 `SYNC.md`。

## 构建

```bash
cd packages/api-sdk
pnpm install
pnpm build        # 产出 dist/ (ESM + CJS + .d.ts)
pnpm typecheck    # 类型检查
pnpm exec tsx scripts/test-token-refresh.ts   # 跑 refresh / dedupe / hooks / retry / 多实例 9 个场景
```

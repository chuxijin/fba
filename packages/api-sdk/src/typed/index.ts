/**
 * 类型对齐工具: 把 hey-api generated 的 ResponseSchemaModel<T> 形态自动 unwrap 成 T
 *
 * 背景:
 *   - generated 方法返回 Promise<{ data: ResponseSchemaModel<T>, status, ... }>
 *   - SDK 拦截器运行时把 axios response.data 拆包成内层 T (兼容旧调用方式)
 *   - 但 TypeScript 仍按 generated 签名认为 .data 是 ResponseSchemaModel<T>
 *   - → 业务侧只能 `as any` 跳过类型检查
 *
 * 解决:
 *   把方法集合做一次纯类型层面的 cast, 类型上的 .data 与运行时的 .data 对齐
 *   运行时 0 开销 (没有 Proxy / 没有 wrapper), 只是 type assertion
 *
 * 使用:
 *   ```ts
 *   import * as g from '@fba/api-sdk/generated'
 *   import { typed } from '@fba/api-sdk'
 *
 *   export const api = typed(g)
 *
 *   const { data } = await api.qbankGetBank({ path: { pk: 1 } })
 *   //      ^? GetBankDetailWithChapters  (不再是 ResponseSchemaModelGetBankDetailWithChapters)
 *   ```
 */

/**
 * 后端 ResponseSchemaModel 的结构特征: 必有 `data` 字段 + 通常带 `code` / `msg`
 *
 * 若 T 长这样 → 解开内层 data; 否则原样返回
 */
type UnwrapResponseModel<T> = T extends { code?: number, msg?: string, data: infer D }
  ? D
  : T extends { data: infer D, code?: unknown, msg?: unknown }
    ? D
    : T

/**
 * 把 axios 风格的 Promise<{ data: ResponseSchemaModel<T>, ... }> 转成 Promise<{ data: T, ... }>
 *
 * hey-api 在 ThrowOnError=false 时, data 是 optional; SDK 拦截器强制 reject 错误,
 * 所以这里假设业务侧拿到的 data 一定存在 (NonNullable)
 */
type ForceUnwrapAxiosData<R> = R extends Promise<infer Res>
  ? Res extends { data?: infer D }
    ? Promise<Omit<Res, 'data'> & { data: UnwrapResponseModel<NonNullable<D>> }>
    : R
  : R

/** 整个方法集合自动 unwrap; 非函数成员原样保留 */
export type UnwrappedApi<T> = {
  [K in keyof T]: T[K] extends (...args: infer A) => infer R
    ? (...args: A) => ForceUnwrapAxiosData<R>
    : T[K]
}

/** 把 generated 模块包成类型对齐版本; 运行时 noop, 纯 type assertion */
export function typed<T>(module: T): UnwrappedApi<T> {
  return module as unknown as UnwrappedApi<T>
}

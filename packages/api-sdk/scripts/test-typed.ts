/**
 * typed() 类型对齐的编译期断言
 *
 * 这个文件只通过 `tsc --noEmit` 验证类型, 没有运行时行为
 * 如果类型映射出错, tsc 会报错
 */

import * as g from '../src/generated'
import { typed } from '../src/typed'
import type { GetBankDetailWithChapters } from '../src/generated'

const api = typed(g)

async function assertTypes() {
  // 1) qbankGetBank: ResponseSchemaModelGetBankDetailWithChapters → GetBankDetailWithChapters
  const res = await api.qbankGetBank({ path: { pk: 1 } })
  const data: GetBankDetailWithChapters = res.data

  // ts-expect-error: data 不应该再是 ResponseSchemaModelGetBankDetailWithChapters,
  // 即下面这行应该编译失败 (我们不期望 data 有 code/msg 字段)
  // 注意: 这里用 @ts-expect-error 的反向断言, 如果 data 仍然是 ResponseModel 形态,
  // 编译会失败抛出 "Unused @ts-expect-error directive"
  // @ts-expect-error - 期望 data 不是 ResponseSchemaModel 包装
  const _shouldFail: { code: number, msg: string } = res.data

  // 用 chapters 字段验证 data 类型确实是 GetBankDetailWithChapters
  if (data.chapters) {
    console.log('chapters:', data.chapters.length)
  }
}

// 防止编译器优化掉
void assertTypes

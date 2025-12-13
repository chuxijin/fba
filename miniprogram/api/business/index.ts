/**
 * 业务 API 统一导出
 */

export * from './bank'
export * from './category'
export * from './chapter'
export * from './question'
export * from './question-v2'
export * from './favorite'

// 默认导出
import * as bankApi from './bank'
import * as categoryApi from './category'
import * as chapterApi from './chapter'
import * as questionApi from './question'
import * as questionV2Api from './question-v2'
import * as favoriteApi from './favorite'

export default {
  bank: bankApi,
  category: categoryApi,
  chapter: chapterApi,
  question: questionApi,
  questionV2: questionV2Api,
  favorite: favoriteApi,
}

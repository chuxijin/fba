/**
 * 适配器聚合导出中心 (统一对外暴露粉笔、华图及未来其他平台的适配能力)
 */

export * from './types'
export * from './common'

// 题库命名空间导出
import * as fenbi from './fenbi'
import * as huatu from './huatu'
import * as shikaobang from './shikaobang'

export { fenbi, huatu, shikaobang }

// 顶级快捷直接导出
export {
  adaptFenbiPaper,
  backfillPaperAnswers,
  fetchFenbiPaperActively,
  extractFenbiPaperFromDom,
  setCachedKeypointTree,
  getCachedKeypointTree,
  parseMistakePageMeta,
  fetchMistakeQuestionsByCount,
  fenbiSession,
} from './fenbi'

export {
  adaptHuatuPaper,
  parseHuatuQuestionDetail,
  fetchHuatuPaperActively,
  extractHuatuPaperFromDom,
  parseHuatuMistakePageMeta,
  fetchHuatuMistakeQuestionsByCount,
} from './huatu'

export {
  adaptShikaobangPaper,
  parseQuillDelta,
  fetchShikaobangPaperActively,
  extractShikaobangPaperFromDom,
  parseShikaobangMistakePageMeta,
  fetchShikaobangMistakeQuestionsByCount,
} from './shikaobang'

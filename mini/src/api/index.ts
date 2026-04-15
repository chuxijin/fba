import { fbaApi } from './sdk'

// 导出所有自动生成的类型
export type * from '@fba/api-sdk'

// 题库 API
export const bankApi = {
  getBankList: fbaApi.qbank.bank.getList,
  getBankDetail: fbaApi.qbank.bank.getDetail,
  getRecommendBanks: fbaApi.qbank.bank.getRecommend,
}

// 分类 API
export const categoryApi = {
  getCategoryTree: async (params: any) => {
    // 调用原来后端的对应分类接口（需确认 SDK 的具体实现）
    // 假设在 admin 或 gongkao 这里有对应的，如果没有则由于统一了需要使用 SDK 的原本方法。
    // 如果 SDK 没有单独的 getCategoryTree，这里只是举个桥接的例子
    return [] // 临时 Mock 需替换为 SDK 实现
  },
}

// 题目API V2 (刷题专用)
export const questionApiV2 = {
  // getPracticeQuestions 等方法
  getQuestions: fbaApi.qbank.practice.getQuestions,
  queryQuestions: fbaApi.qbank.practice.getQuestions,
  getPracticeQuestions: fbaApi.qbank.practice.getQuestions,
  getBankPracticeQuestions: fbaApi.qbank.practice.getQuestionsByBank,
  getChapterPracticeQuestions: fbaApi.qbank.practice.getQuestionsByChapter,
  getPracticeQuestionDetail: fbaApi.qbank.practice.getQuestionDetail,
  getQuestionAnalysis: fbaApi.qbank.practice.getQuestionAnalysis,

  // 原有的 submitAnswers 实际上在 SDK 里是针对 session 操作
  // submitAnswers: fbaApi.qbank.practice.submitSession
}

// 题目筛选 API
export const questionApi = {
  getDetail: fbaApi.qbank.question.getDetail,
  getList: fbaApi.qbank.question.getList,
  getCollections: fbaApi.qbank.question.getCollections,
  collect: fbaApi.qbank.question.collect,
  getAnalysis: fbaApi.qbank.question.getAnalysis,
  getSolution: fbaApi.qbank.question.getSolution,
  checkFavorites: fbaApi.qbank.question.checkFavorites,
  getNotes: fbaApi.qbank.question.getNotes,
}

// 认证 API
export const authApi = {
  wxLogin: fbaApi.qbank.auth.wxLogin,
  login: fbaApi.admin.auth.login,
  getCurrentUser: fbaApi.qbank.auth.getMe,
}

export const ossApi = {
  upload: async (...args: any[]) => {
    const ossModule = (fbaApi as any)?.oss
    if (!ossModule || typeof ossModule.upload !== 'function') {
      throw new Error('OSS_SDK_MODULE_NOT_READY')
    }
    return ossModule.upload(...args)
  },
}

// 首页相关
export const homeApi = {
  getHomeDashboard: fbaApi.qbank.home.getDashboard,
  checkIn: fbaApi.qbank.home.checkIn,
  getCheckInCalendar: fbaApi.qbank.home.getCheckInCalendar,
  getRank: (params?: any) => fbaApi.qbank.home.getRank(params?.rank_type, params?.limit),
}

// 会话 & 练习 API
export const practiceApi = {
  getUserStatistics: fbaApi.qbank.home.getDashboard, // 老版本可能是从这获取的
  createPracticeSession: fbaApi.qbank.session.create,
  verifyAnswer: fbaApi.qbank.session.upsertRecords,
  submitPracticeSession: fbaApi.qbank.session.submit,
  getPracticeSessionDetail: fbaApi.qbank.session.getDetail,
  getPracticeRecords: fbaApi.qbank.session.getRecords,
  getSessionReport: fbaApi.qbank.session.getReport,
  getSessionSolution: fbaApi.qbank.session.getSolution,
  resumePracticeSession: (id: number) => fbaApi.qbank.session.getDetail(id),
  deleteSession: fbaApi.qbank.session.remove,
}

// 因为这里为了兼容老代码会花费大量精力，我们更推荐直接在页面中采用 SDK
// 因此下方我们可以直接导出 fbaApi
export { fbaApi }

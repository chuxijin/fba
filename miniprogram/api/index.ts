/**
 * API 统一出口（重构后）
 */

// 导出请求工具
export { default as request, setToken, clearToken } from './request'
export { get, post, put, del as delete, patch } from './request'

// 导出通用类型
export type * from './types'
export type * from './types/question-v2'

// 导出业务 API
export * as bankApi from './business/bank'
export * as categoryApi from './business/category'
export * as chapterApi from './business/chapter'
export * as questionApi from './business/question'
export * as questionApiV2 from './business/question-v2'
export * as practiceApi from './business/practice'
export * as favoriteApi from './business/favorite'

// 导出系统 API
export * as authApi from './system/auth'
export * as customerApi from './system/customer'

// 使用示例：
// import { authApi, bankApi, questionApiV2, setToken } from '@/api'
//
// // 登录
// const res = await authApi.testLogin({ username: 'test' })
// setToken(res.access_token)
//
// // 获取题库列表
// const banks = await bankApi.getBankList()
//
// // 【新】获取刷题专用题目列表（推荐使用 v2）
// const questions = await questionApiV2.getBankPracticeQuestions(1, { type: 'single' })
//
// // 或者直接导入
// import { testLogin } from '@/api/system/auth'
// import { getBankList } from '@/api/business/bank'
// import { getBankPracticeQuestions } from '@/api/business/question-v2'
// const res = await testLogin({ username: 'test' })
// const banks = await getBankList()
// const questions = await getBankPracticeQuestions(1)

/**
 * 题目相关 API（对接重构后的后端）
 */

import { get, post } from './request'
import type {
  QuestionListItem,
  QuestionDetail,
  QuestionAnalysisDetail,
  QuestionQueryParams,
  BatchSubmitAnswerParam,
  BatchSubmitAnswerResult,
} from './types/question-v2'

/** ==================== 刷题相关接口 ==================== */

/**
 * 获取练习题目列表（刷题专用）
 *
 * @param params 查询参数
 * @return 题目列表（不含答案）
 */
export function getPracticeQuestions(params?: QuestionQueryParams) {
  return get<QuestionListItem[]>('/qbank/practice/questions', params, {
    needToken: true,
  })
}

/**
 * 获取指定题库的题目列表（刷题专用）
 *
 * @param bankId 题库 ID
 * @param params 其他查询参数
 * @return 题目列表（不含答案）
 */
export function getBankPracticeQuestions(
  bankId: number,
  params?: Omit<QuestionQueryParams, 'bank_id'>
) {
  return get<QuestionListItem[]>(
    `/qbank/practice/banks/${bankId}/questions`,
    params,
    {
      needToken: true,
    }
  )
}

/**
 * 获取指定章节的题目列表（刷题专用）
 *
 * @param chapterId 章节 ID
 * @param params 其他查询参数
 * @return 题目列表（不含答案）
 */
export function getChapterPracticeQuestions(
  chapterId: number,
  params?: Omit<QuestionQueryParams, 'chapter_id'>
) {
  return get<QuestionListItem[]>(
    `/qbank/practice/chapters/${chapterId}/questions`,
    params,
    {
      needToken: true,
    }
  )
}

/**
 * 获取题目详情（刷题专用，不含答案）
 *
 * @param questionId 题目 ID
 * @return 题目详情
 */
export function getPracticeQuestionDetail(questionId: number) {
  return get<QuestionDetail>(`/qbank/practice/questions/${questionId}`, undefined, {
    needToken: true,
  })
}

/**
 * 获取题目解析（含答案）
 *
 * @param questionId 题目 ID
 * @return 题目解析
 */
export function getQuestionAnalysis(questionId: number) {
  return get<QuestionAnalysisDetail>(
    `/qbank/practice/questions/${questionId}/analysis`,
    undefined,
    {
      needToken: true,
    }
  )
}

/**
 * 批量提交答案
 *
 * @param data 提交数据
 * @return 判分结果
 */
export function submitAnswers(data: BatchSubmitAnswerParam) {
  return post<BatchSubmitAnswerResult>('/qbank/practice/submit', data, {
    needToken: true,
  })
}

/** ==================== 管理端接口 ==================== */

/**
 * 获取题目列表（管理端）
 *
 * @param params 查询参数
 * @return 题目列表
 */
export function getQuestionList(params?: QuestionQueryParams) {
  return get<QuestionListItem[]>('/qbank/questions', params, {
    needToken: true,
  })
}

/**
 * 获取题目详情（管理端，含答案）
 *
 * @param questionId 题目 ID
 * @return 题目详情
 */
export function getQuestionDetail(questionId: number) {
  return get<QuestionDetail>(`/qbank/questions/${questionId}`, undefined, {
    needToken: true,
  })
}

/** 导出为默认对象 */
export default {
  // 刷题接口
  getPracticeQuestions,
  getBankPracticeQuestions,
  getChapterPracticeQuestions,
  getPracticeQuestionDetail,
  getQuestionAnalysis,
  submitAnswers,
  // 管理接口
  getQuestionList,
  getQuestionDetail,
}

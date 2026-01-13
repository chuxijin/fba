/**
 * 题目相关 API（对接重构后的后端）
 */

import { get, post } from '../request'
import type {
  QuestionListItem,
  QuestionWithAnswer,
  QuestionDetail,
  QuestionAnalysisDetail,
  QuestionSolution,
  QuestionQueryParams,
  BatchSubmitAnswerParam,
  BatchSubmitAnswerResult,
} from '../types/question-v2'

/** ==================== 刷题相关接口 ==================== */

/**
 * 批量获取题目列表（通过 ID 列表）- 不含答案
 *
 * @param params 查询参数（ids 为必填，include_answer 为 false 或不传）
 * @return 题目列表（不含答案）
 */
export function getQuestions(params: { ids: string; include_answer?: false }): Promise<QuestionListItem[]>

/**
 * 批量获取题目列表（通过 ID 列表）- 含答案
 *
 * @param params 查询参数（ids 为必填，include_answer 为 true）
 * @return 题目列表（含答案和解析）
 */
export function getQuestions(params: { ids: string; include_answer: true }): Promise<QuestionWithAnswer[]>

/**
 * 批量获取题目列表（通过 ID 列表）- 实现
 */
export function getQuestions(
  params: { ids: string; include_answer?: boolean }
): Promise<QuestionListItem[] | QuestionWithAnswer[]> {
  return get<QuestionListItem[] | QuestionWithAnswer[]>('/qbank/questions', params, {
    needToken: true,
  })
}

/**
 * 查询题目列表（通过题库/章节等条件）- 不含答案
 *
 * @param params 查询参数
 * @return 题目列表（不含答案）
 */
export function queryQuestions(params: QuestionQueryParams & { include_answer?: false }): Promise<QuestionListItem[]>

/**
 * 查询题目列表（通过题库/章节等条件）- 含答案
 *
 * @param params 查询参数
 * @return 题目列表（含答案和解析）
 */
export function queryQuestions(params: QuestionQueryParams & { include_answer: true }): Promise<QuestionWithAnswer[]>

/**
 * 查询题目列表（通过题库/章节等条件）- 实现
 */
export function queryQuestions(
  params: QuestionQueryParams & { include_answer?: boolean }
): Promise<QuestionListItem[] | QuestionWithAnswer[]> {
  return get<QuestionListItem[] | QuestionWithAnswer[]>('/qbank/questions', params, {
    needToken: true,
  })
}

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
 * 获取题目答案和解析（练题模式专用）
 *
 * @param questionId 题目 ID
 * @param userAnswer 用户答案（可选，传入时会返回判题结果）
 * @return 题目答案和解析
 */
export function getQuestionSolution(questionId: number, userAnswer?: string) {
  return get<QuestionSolution>(
    `/qbank/questions/${questionId}/solution`,
    userAnswer ? { user_answer: userAnswer } : undefined,
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
  getQuestions,
  queryQuestions,
  getPracticeQuestions,
  getBankPracticeQuestions,
  getChapterPracticeQuestions,
  getPracticeQuestionDetail,
  getQuestionAnalysis,
  getQuestionSolution,
  submitAnswers,
  // 管理接口
  getQuestionList,
  getQuestionDetail,
}

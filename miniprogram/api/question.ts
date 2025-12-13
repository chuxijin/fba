/**
 * 题目相关 API
 */

import { get } from './request'
import type { QuestionDetail } from './types/question'

/** ==================== 类型定义 ==================== */

/** 题目简要信息（列表用） */
export interface QuestionSimple {
  /** 题目 ID */
  id: number
  /** 题库 ID */
  bank_id: number
  /** 章节 ID */
  chapter_id: number | null
  /** 题型 ID */
  type_id: number
  /** 选择题类型 */
  choice_type: string | null
  /** 难度 ID */
  diff_id: number | null
  /** 题干 */
  stem: string
  /** 分值 */
  score: number
  /** 是否启用 */
  is_active: boolean
  /** 审核状态 */
  review_status: number
  /** 创建时间 */
  created_time: string
}

/** 获取题目列表参数 */
export interface GetQuestionListParams {
  /** 题库 ID */
  bank_id?: number
  /** 章节 ID */
  chapter_id?: number
  /** 题型 ID */
  type_id?: number
  /** 难度 ID */
  diff_id?: number
  /** 是否启用 */
  is_active?: boolean
  /** 审核状态 */
  review_status?: number
  /** 关键字搜索 */
  keyword?: string
}

/** ==================== API 方法 ==================== */

/**
 * 获取题目详情
 *
 * :param pk: 题目 ID
 * :return:
 */
export function getQuestionDetail(pk: number) {
  return get<QuestionDetail>(`/qbank/practice/questions/${pk}`, undefined, {
    needToken: true,
  })
}

/**
 * 获取题库的题目列表（刷题专用）
 *
 * :param bankId: 题库 ID
 * :return:
 */
export function getBankQuestions(bankId: number) {
  return get<QuestionDetail[]>(`/qbank/practice/banks/${bankId}/questions`, undefined, {
    needToken: true,
  })
}

/**
 * 获取章节的题目列表（刷题专用）
 *
 * :param chapterId: 章节 ID
 * :return:
 */
export function getChapterQuestions(chapterId: number) {
  return get<QuestionDetail[]>(`/qbank/practice/chapters/${chapterId}/questions`, undefined, {
    needToken: true,
  })
}

/**
 * 获取题目列表（管理端用）
 *
 * :param params: 查询参数
 * :return:
 */
export function getQuestionList(params: GetQuestionListParams) {
  return get<QuestionDetail[]>('/qbank/questions', params, {
    needToken: true,
  })
}

/** 导出为默认对象 */
export default {
  getQuestionDetail,
  getBankQuestions,
  getChapterQuestions,
  getQuestionList,
}

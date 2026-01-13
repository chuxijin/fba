/**
 * 错题本相关 API
 */

import { get, post, put, del } from '../request'

/** ==================== 类型定义 ==================== */

/** 错题项详情 */
export interface WrongQuestionItem {
  /** 错题记录 ID */
  id: number
  /** 题目 ID */
  question_id: number
  /** 错误次数 */
  wrong_count: number
  /** 连续做对次数 */
  correct_count: number
  /** 最后一次错误时间 */
  last_wrong_time: string
  /** 是否已掌握（连续答对3次） */
  is_mastered: boolean
  /** 是否置顶 */
  is_pinned: boolean

  /** 题目题干（关联查询） */
  question_stem: string | null
  /** 题型 */
  question_type: string | null
  /** 题库 ID */
  bank_id?: number
  /** 题库名称 */
  bank_name: string | null
  /** 章节 ID */
  chapter_id?: number
  /** 章节名称 */
  chapter_name: string | null
  /** 分类 ID */
  cat_id?: number
  /** 分类名称 */
  cat_name: string | null
}

/** 错题列表响应 */
export interface WrongQuestionListResponse {
  /** 错题列表 */
  items: WrongQuestionItem[]
  /** 总数 */
  total: number
  /** 当前页 */
  page: number
  /** 每页数量 */
  size: number
}

/** 获取错题列表参数 */
export interface GetWrongQuestionListParams {
  /** 是否已掌握（筛选） */
  is_mastered?: boolean
  /** 是否置顶（筛选） */
  is_pinned?: boolean
  /** 页码 */
  page?: number
  /** 每页数量 */
  size?: number
}

/** 错题统计 */
export interface WrongQuestionStatistics {
  /** 错题总数 */
  total_count: number
  /** 已掌握数量 */
  mastered_count: number
  /** 未掌握数量 */
  unmastered_count: number
  /** 平均错误次数 */
  avg_wrong_count: number
}

/** ==================== API 函数 ==================== */

/**
 * 获取错题列表（分页）
 */
export async function getWrongQuestionList(
  params: GetWrongQuestionListParams = {}
): Promise<WrongQuestionListResponse> {
  return get('/qbank/wrong-questions', params)
}

/**
 * 获取错题详情
 */
export async function getWrongQuestionDetail(wrongId: number): Promise<WrongQuestionItem> {
  return get(`/qbank/wrong-questions/${wrongId}`)
}

/**
 * 获取错题统计
 */
export async function getWrongQuestionStatistics(): Promise<WrongQuestionStatistics> {
  return get('/qbank/wrong-questions/statistics')
}

/**
 * 设置错题置顶
 */
export async function setWrongQuestionPin(wrongId: number, isPinned: boolean): Promise<void> {
  return put(`/qbank/wrong-questions/${wrongId}/pin`, { is_pinned: isPinned })
}

/**
 * 从错题本移除（单个）
 */
export async function deleteWrongQuestion(wrongId: number): Promise<void> {
  return del(`/qbank/wrong-questions/${wrongId}`)
}

/**
 * 批量删除错题
 */
export async function batchDeleteWrongQuestions(wrongIds: number[]): Promise<void> {
  return post('/qbank/wrong-questions/batch-delete', { wrong_ids: wrongIds })
}

/**
 * 清空已掌握的错题
 */
export async function clearMasteredWrongQuestions(): Promise<void> {
  return post('/qbank/wrong-questions/clear-mastered', {})
}

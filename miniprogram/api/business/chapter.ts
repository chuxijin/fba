/**
 * 章节相关 API
 */

import { get } from '../request'

/** ==================== 类型定义 ==================== */

/** 章节详情 */
export interface ChapterDetail {
  /** 章节 ID */
  id: number
  /** 题库 ID */
  bank_id: number
  /** 父级章节 ID */
  parent_id: number | null
  /** 章节名称 */
  name: string
  /** 章节编号 */
  code: string | null
  /** 排序 */
  sort: number
  /** 是否试用章节 */
  is_trial: boolean
  /** 题目数量 */
  q_count: number
  /** 创建时间 */
  created_time: string
  /** 更新时间 */
  updated_time: string | null
  /** 子章节列表 */
  children?: ChapterDetail[]
}

/** ==================== API 方法 ==================== */

/**
 * 获取题库章节树（客户端公开接口）
 */
export function getChapterTree(bankId: number) {
  return get<ChapterDetail[]>(`/qbank/chapters/tree/customer`, { bank_id: bankId }, {
    needToken: false,
  })
}

/**
 * 获取章节详情
 */
export function getChapterDetail(pk: number) {
  return get<ChapterDetail>(`/qbank/chapters/${pk}`, undefined, {
    needToken: true,
  })
}

/** 导出为默认对象 */
export default {
  getChapterTree,
  getChapterDetail,
}

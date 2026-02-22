/**
 * 题库相关 API
 */

import { get } from '../request'

/** ==================== 类型定义 ==================== */

/** 章节树节点 */
export interface ChapterTreeNode {
  /** 章节 ID */
  id: number
  /** 章节名称 */
  name: string
  /** 章节描述 */
  desc?: string | null
  /** 题目数量 */
  q_count: number
  /** 排序值 */
  sort_order: number
  /** 是否试用章节 */
  is_trial: boolean
  /** 子章节列表 */
  children?: ChapterTreeNode[]
}

/** 题库详情 */
export interface BankDetail {
  /** 题库 ID */
  id: number
  /** 所属分类 ID */
  cat_id: number
  /** 题库名称 */
  name: string
  /** 题库编码 */
  code: string
  /** 题库描述 */
  desc: string | null
  /** 封面地址 */
  cover_url: string | null
  /** 难度字典 ID */
  diff_id: number | null
  /** 类型: 10=题库(含题目), 20=合集(含子题库) */
  type: number
  /** 父级题库 ID */
  parent_id: number | null
  /** 题库状态 */
  status: number
  /** 可见范围 */
  scope: number
  /** 题目数量 */
  q_count: number
  /** 题库总分 */
  total_score: number
  /** 购买数量 */
  buy_count: number
  /** 创建时间 */
  created_time: string
  /** 更新时间 */
  updated_time: string | null
  /** 子题库列表（树形结构） */
  children?: BankDetail[]
  /** 章节树（含章节树时返回） */
  chapters?: ChapterTreeNode[]
}

/** 获取题库列表参数 */
export interface GetBankListParams {
  /** 分类 ID */
  cat_id?: number
  /** 题库状态 */
  status?: number
  /** 可见范围 */
  scope?: number
  /** 关键字搜索 */
  keyword?: string
}

/** ==================== API 方法 ==================== */

/**
 * 获取题库详情
 *
 * :param pk: 题库 ID
 * :return:
 */
export function getBankDetail(pk: number) {
  return get<BankDetail>(`/qbank/banks/${pk}`, undefined, {
    needToken: false,
  })
}

/**
 * 获取题库树形列表
 *
 * :param params: 查询参数
 * :return:
 */
export function getBankList(params?: GetBankListParams) {
  return get<BankDetail[]>('/qbank/banks', params, {
    needToken: false,
  })
}

/**
 * 获取推荐题库（全局热门）
 *
 * 返回最近7天全站做题最多的前5个题库
 *
 * :return:
 */
export function getRecommendBanks() {
  return get<BankDetail[]>('/qbank/banks/recommend', undefined, {
    needToken: false,
  })
}

/** 导出为默认对象 */
export default {
  getBankDetail,
  getBankList,
  getRecommendBanks,
}

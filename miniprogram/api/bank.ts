/**
 * 题库相关 API
 */

import { get } from './request'

/** ==================== 类型定义 ==================== */

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

/** 导出为默认对象 */
export default {
  getBankDetail,
  getBankList,
}

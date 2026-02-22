/**
 * 分类相关 API（使用系统分类）
 */

import { get } from '../request'

/** ==================== 类型定义 ==================== */

/** 分类详情 */
export interface CategoryDetail {
  id: number
  app_code: string
  name: string
  type: string
  code: string | null
  description: string | null
  parent_id: number | null
  level: number
  icon: string | null
  color: string | null
  sort_order: number
  status: boolean
  created_time: string
  updated_time: string | null
  children?: CategoryDetail[]
}

/** 获取分类树参数 */
export interface GetCategoryTreeParams {
  app_code?: string
  type?: string
  status?: boolean
}

/** ==================== API 方法 ==================== */

/**
 * 获取分类详情
 */
export function getCategoryDetail(pk: number) {
  return get<CategoryDetail>(`/sys/categories/${pk}`)
}

/**
 * 获取分类树
 */
export function getCategoryTree(params?: GetCategoryTreeParams) {
  return get<CategoryDetail[]>('/sys/categories/tree', params)
}

/** 导出为默认对象 */
export default {
  getCategoryDetail,
  getCategoryTree,
}

/**
 * 分类相关 API
 */

import { get } from '../request'

/** ==================== 类型定义 ==================== */

/** 分类详情 */
export interface CategoryDetail {
  /** 分类 ID */
  id: number
  /** 分类名称 */
  name: string
  /** 分类类型（0=全部 1=题库 2=词库 3=资料包 4=商城） */
  cat_type: number
  /** 分类编码 */
  code: string
  /** 分类层级 */
  level: number
  /** 是否启用 */
  is_active: boolean
  /** 排序权重 */
  sort_order: number
  /** 父级分类 ID */
  parent_id: number | null
  /** 创建时间 */
  created_time: string
  /** 更新时间 */
  updated_time: string | null
  /** 子分类列表（树形结构） */
  children?: CategoryDetail[]
}

/** 获取分类树参数 */
export interface GetCategoryTreeParams {
  /** 分类类型 */
  cat_type?: number
  /** 是否启用 */
  is_active?: boolean
}

/** ==================== API 方法 ==================== */

/**
 * 获取分类详情
 *
 * :param pk: 分类 ID
 * :return:
 */
export function getCategoryDetail(pk: number) {
  return get<CategoryDetail>(`/qbank/categories/${pk}`, undefined, {
    needToken: false,
  })
}

/**
 * 获取分类树
 *
 * :param params: 查询参数
 * :return:
 */
export function getCategoryTree(params?: GetCategoryTreeParams) {
  return get<CategoryDetail[]>('/qbank/categories', params, {
    needToken: false,
  })
}

/** 导出为默认对象 */
export default {
  getCategoryDetail,
  getCategoryTree,
}

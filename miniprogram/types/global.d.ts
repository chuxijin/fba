/**
 * 全局类型定义
 */

/**
 * uni-app 全局声明
 */
declare const uni: any

/**
 * 当前页面实例
 */
declare function getCurrentPages(): any[]

/**
 * 通用分页参数
 */
export interface PageParams {
  /** 页码 */
  page?: number
  /** 每页数量 */
  pageSize?: number
  /** 排序字段 */
  orderBy?: string
  /** 排序方式 */
  order?: 'asc' | 'desc'
}

/**
 * 通用分页数据
 */
export interface PageData<T> {
  /** 数据列表 */
  items: T[]
  /** 总条数 */
  total: number
  /** 当前页码 */
  page: number
  /** 每页数量 */
  pageSize: number
  /** 总页数 */
  totalPages: number
}

/**
 * API 响应基础结构
 */
export interface ApiResponse<T = any> {
  /** 状态码 */
  code: number
  /** 消息 */
  msg: string
  /** 数据 */
  data: T
}

/**
 * 通用 ID 类型
 */
export type ID = number | string

/**
 * 通用状态类型
 */
export type Status = 0 | 1

/**
 * 主题类型
 */
export type Theme = 'light' | 'dark'

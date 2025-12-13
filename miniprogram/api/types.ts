/**
 * API 通用类型定义
 */

/** HTTP 请求方法 */
export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'

/** 请求配置 */
export interface RequestConfig {
  /** 请求地址 */
  url: string
  /** 请求方法 */
  method?: HttpMethod
  /** 请求数据 */
  data?: any
  /** URL 查询参数 */
  params?: Record<string, any>
  /** 请求头 */
  header?: Record<string, string>
  /** 超时时间（毫秒） */
  timeout?: number
  /** 是否需要 Token */
  needToken?: boolean
  /** 是否显示 loading */
  showLoading?: boolean
  /** loading 提示文字 */
  loadingText?: string
}

/** 后端统一响应格式 */
export interface ApiResponse<T = any> {
  /** 响应码 */
  code: number
  /** 响应消息 */
  msg: string
  /** 响应数据 */
  data: T
}

/** 分页请求参数 */
export interface PageParams {
  /** 页码（从 1 开始） */
  page?: number
  /** 每页数量 */
  pageSize?: number
}

/** 分页响应数据 */
export interface PageData<T = any> {
  /** 总记录数 */
  total: number
  /** 当前页数据 */
  list: T[]
  /** 当前页码 */
  page?: number
  /** 每页数量 */
  pageSize?: number
}

/** 后端统一响应结构 */
export interface ResponseModel<T = unknown> {
  code: number;
  msg: string;
  data: T;
}

/** 后端分页数据结构 */
export interface PageData<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  total_pages: number;
}

/** 通用删除参数 */
export interface DeleteParam {
  ids: number[];
}

/** 通用分页参数 */
export interface PaginationParams {
  page?: number;
  size?: number;
}

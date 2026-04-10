import type { AxiosInstance } from 'axios';
import type { ContentResult, ContentParams, ContentListDetail } from '../types/content';
import type { ResponseModel, PageData } from '../types/common';
import type { ApiClient } from '../client/types';

export interface ContentModule {
  /**
   * 获取内容列表(分页)
   * @param params 查询参数
   */
  getList(params?: ContentParams): Promise<ResponseModel<PageData<ContentListDetail>>>;

  /**
   * 获取内容详情
   * @param id 内容 ID
   */
  getDetail(id: number): Promise<ResponseModel<ContentResult>>;

  /**
   * 创建内容
   * @param data 内容数据
   */
  create(data: Partial<ContentResult>): Promise<ResponseModel<void>>;

  /**
   * 更新内容
   * @param id 内容 ID
   * @param data 更新的数据
   */
  update(id: number, data: Partial<ContentResult>): Promise<ResponseModel<void>>;

  /**
   * 删除内容
   * @param ids ID 列表
   */
  delete(ids: number[]): Promise<ResponseModel<void>>;
}

export const createContentModule = (request: ApiClient): ContentModule => ({
  getList(params) {
    return request.get<ResponseModel<PageData<ContentListDetail>>>('/content/list', { params: params as Record<string, unknown> });
  },
  getDetail(id) {
    return request.get<ResponseModel<ContentResult>>(`/content/${id}`);
  },
  create(data) {
    return request.post<ResponseModel<void>>('/content', data);
  },
  update(id, data) {
    return request.put<ResponseModel<void>>(`/content/${id}`, data);
  },
  delete(ids) {
    return request.delete<ResponseModel<void>>('/content', { params: { pk: ids } });
  },
});

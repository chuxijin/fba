import type { ApiClient } from '../client/types';
import type {
  CreateMaterialParam,
  GetMaterialDetail,
  GetMaterialListItem,
  GetMaterialWithRelationDetail,
  LinkQuestionParam,
  MaterialListParams,
  UpdateMaterialParam,
} from '../types';

export interface MaterialModule {
  /** 获取材料详情（含关联信息�?*/
  getDetail(id: number): Promise<GetMaterialWithRelationDetail>;
  /** 获取材料列表 */
  getList(params?: MaterialListParams): Promise<GetMaterialListItem[]>;
  /** 获取指定题库的材料列�?*/
  getByBank(bankId: number, params?: { is_active?: boolean }): Promise<GetMaterialListItem[]>;
  /** 创建材料 */
  create(data: CreateMaterialParam): Promise<GetMaterialDetail>;
  /** 更新材料 */
  update(id: number, data: UpdateMaterialParam): Promise<void>;
  /** 删除材料 */
  remove(ids: number[]): Promise<void>;
  /** 关联题目到材�?*/
  linkQuestions(materialId: number, data: LinkQuestionParam): Promise<void>;
  /** 解除材料与题目关�?*/
  unlinkQuestions(materialId: number, data: LinkQuestionParam): Promise<void>;
}

export function createMaterialModule(client: ApiClient): MaterialModule {
  return {
    getDetail(id) {
      return client.get<GetMaterialWithRelationDetail>(`/materials/${id}`);
    },

    getList(params) {
      return client.get<GetMaterialListItem[]>('/materials', { params: params as Record<string, unknown> });
    },

    getByBank(bankId, params) {
      return client.get<GetMaterialListItem[]>(`/materials/bank/${bankId}`, {
        params: params as Record<string, unknown>,
      });
    },

    create(data) {
      return client.post<GetMaterialDetail>('/materials', data);
    },

    update(id, data) {
      return client.put(`/materials/${id}`, data);
    },

    remove(ids) {
      return client.delete('/materials', { ids });
    },

    linkQuestions(materialId, data) {
      return client.post(`/materials/${materialId}/link`, data);
    },

    unlinkQuestions(materialId, data) {
      return client.post(`/materials/${materialId}/unlink`, data);
    },
  };
}


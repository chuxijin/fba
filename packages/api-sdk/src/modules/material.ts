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
  /** 获取材料详情（含关联信息） */
  getDetail(id: number): Promise<GetMaterialWithRelationDetail>;
  /** 获取材料列表 */
  getList(params?: MaterialListParams): Promise<GetMaterialListItem[]>;
  /** 获取指定题库的材料列表 */
  getByBank(bankId: number, params?: { is_active?: boolean }): Promise<GetMaterialListItem[]>;
  /** 创建材料 */
  create(data: CreateMaterialParam): Promise<GetMaterialDetail>;
  /** 更新材料 */
  update(id: number, data: UpdateMaterialParam): Promise<void>;
  /** 删除材料 */
  remove(ids: number[]): Promise<void>;
  /** 关联题目到材料 */
  linkQuestions(materialId: number, data: LinkQuestionParam): Promise<void>;
  /** 解除材料与题目关联 */
  unlinkQuestions(materialId: number, data: LinkQuestionParam): Promise<void>;
}

export function createMaterialModule(client: ApiClient): MaterialModule {
  return {
    getDetail(id) {
      return client.get<GetMaterialWithRelationDetail>(`/qbank/materials/${id}`);
    },

    getList(params) {
      return client.get<GetMaterialListItem[]>('/qbank/materials', { params: params as Record<string, unknown> });
    },

    getByBank(bankId, params) {
      return client.get<GetMaterialListItem[]>(`/qbank/materials/bank/${bankId}`, {
        params: params as Record<string, unknown>,
      });
    },

    create(data) {
      return client.post<GetMaterialDetail>('/qbank/materials', data);
    },

    update(id, data) {
      return client.put(`/qbank/materials/${id}`, data);
    },

    remove(ids) {
      return client.delete('/qbank/materials', { ids });
    },

    linkQuestions(materialId, data) {
      return client.post(`/qbank/materials/${materialId}/link`, data);
    },

    unlinkQuestions(materialId, data) {
      return client.post(`/qbank/materials/${materialId}/unlink`, data);
    },
  };
}

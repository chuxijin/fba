import type { ApiClient } from '../client/types';
import type { PageData } from '../types/common';
import type {
  CmsSlotDeletedResult,
  CmsSlotUpdatedResult,
  CreateSlotParam,
  GetActiveSlot,
  GetSlotDetail,
  ReportSlotActionParam,
  SlotListParams,
  SlotStatsResult,
  UpdateSlotParam,
} from '../types/cms';

export interface CmsAdminModule {
  /** 创建运营位 */
  createSlot(data: CreateSlotParam): Promise<GetSlotDetail>;
  /** 更新运营位 */
  updateSlot(pk: number, data: UpdateSlotParam): Promise<CmsSlotUpdatedResult>;
  /** 删除运营位(暂存请用 status=2 下线) */
  deleteSlot(pk: number): Promise<CmsSlotDeletedResult>;
  /** 管理端获取运营位列表 */
  getSlotList(params?: SlotListParams): Promise<PageData<GetSlotDetail>>;
  /** 获取运营位详情 */
  getSlotDetail(pk: number): Promise<GetSlotDetail>;
  /** 获取运营位数据统计 */
  getSlotStats(pk: number, days?: number): Promise<SlotStatsResult>;
}

export interface CmsModule {
  /** 获取场景下命中的运营位列表(用户端) */
  getActiveSlots(scene: string): Promise<GetActiveSlot[]>;
  /** 上报运营位行为(0 曝光 1 点击 2 关闭) */
  reportSlotAction(pk: number, data: ReportSlotActionParam): Promise<void>;
  /** 管理端子模块 */
  admin: CmsAdminModule;
}

export const createCmsModule = (request: ApiClient): CmsModule => {
  const admin: CmsAdminModule = {
    createSlot(data) {
      return request.post<GetSlotDetail>('/cms/admin/slots', data);
    },
    updateSlot(pk, data) {
      return request.put<CmsSlotUpdatedResult>(`/cms/admin/slots/${pk}`, data);
    },
    deleteSlot(pk) {
      return request.delete<CmsSlotDeletedResult>(`/cms/admin/slots/${pk}`);
    },
    getSlotList(params) {
      return request.get<PageData<GetSlotDetail>>('/cms/admin/slots', {
        params: params as Record<string, unknown> | undefined,
      });
    },
    getSlotDetail(pk) {
      return request.get<GetSlotDetail>(`/cms/admin/slots/${pk}`);
    },
    getSlotStats(pk, days = 7) {
      return request.get<SlotStatsResult>(`/cms/admin/slots/${pk}/stats`, {
        params: { days },
      });
    },
  };

  return {
    getActiveSlots(scene) {
      return request.get<GetActiveSlot[]>('/cms/slots/active', {
        params: { scene },
      });
    },
    reportSlotAction(pk, data) {
      return request.post<void>(`/cms/slots/${pk}/log`, data);
    },
    admin,
  };
};

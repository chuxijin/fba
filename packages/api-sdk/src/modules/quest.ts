import type { ApiClient } from '../client/types';
import type { PageData } from '../types/common';
import type {
  AdminClaimListParams,
  CreateQuestParam,
  GetClaimDetail,
  GetQuestDetail,
  GetQuestWithUserDetail,
  MyClaimListParams,
  QuestAbandonResult,
  QuestDeletedResult,
  QuestListParams,
  QuestRetryGrantResult,
  QuestUpdatedResult,
  ReviewClaimParam,
  ReviewClaimResult,
  RevokeClaimParam,
  RevokeClaimResult,
  SubmitClaimParam,
} from '../types/quest';

export interface QuestAdminModule {
  /** 创建任务 */
  createQuest(data: CreateQuestParam): Promise<GetQuestDetail>;
  /** 更新任务 */
  updateQuest(pk: number, data: Partial<CreateQuestParam>): Promise<QuestUpdatedResult>;
  /** 删除任务 */
  deleteQuest(pk: number): Promise<QuestDeletedResult>;
  /** 管理端获取任务列表 */
  getQuestList(params?: QuestListParams): Promise<PageData<GetQuestDetail>>;
  /** 管理端获取领取列表 */
  getClaimList(params?: AdminClaimListParams): Promise<PageData<GetClaimDetail>>;
  /** 审核领取记录 */
  reviewClaim(pk: number, data: ReviewClaimParam): Promise<ReviewClaimResult>;
  /** 重试发放奖励 */
  retryGrantClaim(pk: number): Promise<QuestRetryGrantResult>;
  /** 撤销已审核记录(同时回收奖励) */
  revokeClaim(pk: number, data: RevokeClaimParam): Promise<RevokeClaimResult>;
}

export interface QuestModule {
  /** 用户端获取任务列表 */
  getQuestList(params?: QuestListParams): Promise<PageData<GetQuestDetail>>;
  /** 获取任务详情(含当前用户参与状态) */
  getQuestDetail(pk: number): Promise<GetQuestWithUserDetail>;
  /** 领取任务 */
  claimQuest(pk: number): Promise<GetClaimDetail>;
  /** 提交任务内容 */
  submitClaim(pk: number, data: SubmitClaimParam): Promise<GetClaimDetail>;
  /** 放弃领取 */
  abandonClaim(pk: number): Promise<QuestAbandonResult>;
  /** 获取我的领取列表 */
  getMyClaims(params?: MyClaimListParams): Promise<PageData<GetClaimDetail>>;
  /** 管理端子模块 */
  admin: QuestAdminModule;
}

export const createQuestModule = (request: ApiClient): QuestModule => {
  const admin: QuestAdminModule = {
    createQuest(data) {
      return request.post<GetQuestDetail>('/quest/admin/quests', data);
    },
    updateQuest(pk, data) {
      return request.put<QuestUpdatedResult>(`/quest/admin/quests/${pk}`, data);
    },
    deleteQuest(pk) {
      return request.delete<QuestDeletedResult>(`/quest/admin/quests/${pk}`);
    },
    getQuestList(params) {
      return request.get<PageData<GetQuestDetail>>('/quest/admin/quests', {
        params: params as Record<string, unknown> | undefined,
      });
    },
    getClaimList(params) {
      return request.get<PageData<GetClaimDetail>>('/quest/admin/claims', {
        params: params as Record<string, unknown> | undefined,
      });
    },
    reviewClaim(pk, data) {
      return request.post<ReviewClaimResult>(`/quest/admin/claims/${pk}/review`, data);
    },
    retryGrantClaim(pk) {
      return request.post<QuestRetryGrantResult>(`/quest/admin/claims/${pk}/retry-grant`);
    },
    revokeClaim(pk, data) {
      return request.post<RevokeClaimResult>(`/quest/admin/claims/${pk}/revoke`, data);
    },
  };

  return {
    getQuestList(params) {
      return request.get<PageData<GetQuestDetail>>('/quest/quests', {
        params: params as Record<string, unknown> | undefined,
      });
    },
    getQuestDetail(pk) {
      return request.get<GetQuestWithUserDetail>(`/quest/quests/${pk}`);
    },
    claimQuest(pk) {
      return request.post<GetClaimDetail>(`/quest/quests/${pk}/claim`);
    },
    submitClaim(pk, data) {
      return request.post<GetClaimDetail>(`/quest/claims/${pk}/submit`, data);
    },
    abandonClaim(pk) {
      return request.post<QuestAbandonResult>(`/quest/claims/${pk}/abandon`);
    },
    getMyClaims(params) {
      return request.get<PageData<GetClaimDetail>>('/quest/claims/mine', {
        params: params as Record<string, unknown> | undefined,
      });
    },
    admin,
  };
};

import type { ApiClient } from '../client/types';
import type { PageData } from '../types/common';
import type {
  MembershipBrief,
  MembershipPlanBrief,
  MembershipProgress,
  MembershipRecordBrief,
  MembershipRecordListParams,
  MembershipTierBrief,
} from '../types/membership';
import { createScopedClient, type ScopedApiClient } from './_shared';

export interface MembershipModule {
  request: ScopedApiClient;
  /** 查询当前用户的生效会员列表 */
  getMyMembership(): Promise<MembershipBrief[]>;
  /** 查询当前用户会员经验进度 */
  getMyProgress(familyCode?: string): Promise<MembershipProgress[]>;
  /** 查询当前用户会员流水 */
  getMyRecords(params?: MembershipRecordListParams): Promise<PageData<MembershipRecordBrief>>;
  /** 获取启用会员等级 */
  getActiveTiers(): Promise<MembershipTierBrief[]>;
  /** 获取所有上架会员计划 */
  getAvailablePlans(): Promise<MembershipPlanBrief[]>;
}

export function createMembershipModule(client: ApiClient): MembershipModule {
  const request = createScopedClient(client, '');

  return {
    request,
    getMyMembership() {
      return request.get<MembershipBrief[]>('/membership/me');
    },
    getMyProgress(familyCode?: string) {
      return request.get<MembershipProgress[]>('/membership/me/progress', {
        params: { family_code: familyCode },
      });
    },
    getMyRecords(params = {}) {
      return request.get<PageData<MembershipRecordBrief>>('/membership/me/records', {
        params: params as Record<string, unknown>,
      });
    },
    getActiveTiers() {
      return request.get<MembershipTierBrief[]>('/membership/tiers/active');
    },
    getAvailablePlans() {
      return request.get<MembershipPlanBrief[]>('/membership/plans/available');
    },
  };
}

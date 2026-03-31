import type { ApiClient } from '../client/types';
import type { MembershipBrief, MembershipPlanBrief } from '../types/membership';
import { createScopedClient, type ScopedApiClient } from './_shared';

export interface MembershipModule {
  request: ScopedApiClient;
  /** 查询当前用户的生效会员列表 */
  getMyMembership(): Promise<MembershipBrief[]>;
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
    getAvailablePlans() {
      return request.get<MembershipPlanBrief[]>('/membership/plans/available');
    },
  };
}

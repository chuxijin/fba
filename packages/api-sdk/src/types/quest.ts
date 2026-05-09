import type { PaginationParams } from './common';

/** 任务状态 */
export type QuestStatus = 0 | 1 | 2 | 3;

/** 奖励类型 */
export type QuestRewardType = 'feature' | 'points' | 'vip' | (string & {});

/** 领取状态 */
export type QuestClaimStatus = 0 | 1 | 2 | 3 | 4 | 5 | 6;

/** 奖励发放状态 */
export type QuestRewardStatus = 0 | 1 | 2 | 3;

/** 审核决定 */
export type QuestReviewDecision = 'approve' | 'reject';

/** 创建任务参数 */
export interface CreateQuestParam {
  code: string;
  name: string;
  brief: string;
  info?: string | null;
  detail?: string | null;
  cover_image?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  status?: QuestStatus;
  total_quota?: number;
  max_claims_per_user?: number;
  claim_expire_seconds?: number;
  submission_required?: boolean;
  review_required?: boolean;
  reward_type?: QuestRewardType;
  reward_data?: Record<string, unknown> | null;
  sort?: number;
}

/** 更新任务参数 */
export interface UpdateQuestParam {
  name?: string;
  brief?: string;
  info?: string | null;
  detail?: string | null;
  cover_image?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  status?: QuestStatus;
  total_quota?: number;
  max_claims_per_user?: number;
  claim_expire_seconds?: number;
  submission_required?: boolean;
  review_required?: boolean;
  reward_type?: QuestRewardType;
  reward_data?: Record<string, unknown> | null;
  sort?: number;
}

/** 任务详情 */
export interface GetQuestDetail {
  id: number;
  code: string;
  name: string;
  brief: string;
  info?: string | null;
  detail?: string | null;
  cover_image?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  status: QuestStatus;
  total_quota: number;
  claimed_count: number;
  max_claims_per_user: number;
  claim_expire_seconds: number;
  submission_required: boolean;
  review_required: boolean;
  reward_type: QuestRewardType;
  reward_data?: Record<string, unknown> | null;
  sort: number;
  created_by: number;
  updated_by?: number | null;
  created_time: string;
  updated_time?: string | null;
}

/** 任务详情(含当前用户参与状态) */
export interface GetQuestWithUserDetail extends GetQuestDetail {
  my_claim_count: number;
  my_active_claim_id?: number | null;
  my_latest_claim_status?: QuestClaimStatus | null;
}

/** 任务列表查询参数 */
export interface QuestListParams extends PaginationParams {
  status?: QuestStatus;
  keyword?: string;
  only_active?: boolean;
}

/** 提交任务内容参数 */
export interface SubmitClaimParam {
  submission_links?: string[] | null;
  submission_images?: string[] | null;
  submission_note?: string | null;
}

/** 领取记录详情 */
export interface GetClaimDetail {
  id: number;
  quest_id: number;
  user_id: number;
  claim_status: QuestClaimStatus;
  claim_time?: string | null;
  expire_time?: string | null;
  submission_links?: string[] | null;
  submission_images?: string[] | null;
  submission_note?: string | null;
  submit_time?: string | null;
  review_remark?: string | null;
  reviewed_by?: number | null;
  review_time?: string | null;
  reward_status: QuestRewardStatus;
  granted_at?: string | null;
  created_time: string;
}

/** 领取列表查询参数(用户端"我的") */
export interface MyClaimListParams extends PaginationParams {
  claim_status?: QuestClaimStatus;
}

/** 领取列表查询参数(管理端) */
export interface AdminClaimListParams extends PaginationParams {
  quest_id?: number;
  user_id?: number;
  claim_status?: QuestClaimStatus;
}

/** 审核领取记录参数 */
export interface ReviewClaimParam {
  decision: QuestReviewDecision;
  remark?: string | null;
}

/** 审核结果 */
export interface ReviewClaimResult {
  claim_id: number;
  claim_status: QuestClaimStatus;
  reward_granted: boolean;
  message: string;
}

/** 撤销审核参数 */
export interface RevokeClaimParam {
  remark?: string | null;
}

/** 撤销结果 */
export interface RevokeClaimResult {
  claim_id: number;
  claim_status: QuestClaimStatus;
  reward_revoked: boolean;
  message: string;
}

/** 受影响行数返回结构 */
export interface QuestUpdatedResult {
  updated: number;
}

/** 删除返回结构 */
export interface QuestDeletedResult {
  deleted: number;
}

/** 重试发放结果 */
export interface QuestRetryGrantResult {
  success: boolean;
}

/** 放弃领取返回结构 */
export interface QuestAbandonResult {
  updated: number;
}

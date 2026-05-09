import type { PaginationParams } from './common';

/** 运营位形态 */
export type CmsSlotType =
  | 'banner'
  | 'curtain'
  | 'float'
  | 'notice'
  | 'popup'
  | 'splash'
  | (string & {});

/** 跳转类型 */
export type CmsJumpType =
  | 'content'
  | 'custom'
  | 'miniprogram'
  | 'none'
  | 'quest'
  | 'url'
  | (string & {});

/** 运营位状态 (0 草稿 / 1 上线 / 2 已下线) */
export type CmsSlotStatus = 0 | 1 | 2;

/** 行为类型 (0 曝光 / 1 点击 / 2 关闭) */
export type CmsSlotAction = 0 | 1 | 2;

/** 创建运营位参数 */
export interface CreateSlotParam {
  code: string;
  name: string;
  slot_type: CmsSlotType;
  scene: string;
  title?: string | null;
  subtitle?: string | null;
  image_url?: string | null;
  detail?: string | null;
  jump_type?: CmsJumpType;
  jump_target?: string | null;
  jump_extra?: Record<string, unknown> | null;
  start_time?: string | null;
  end_time?: string | null;
  status?: CmsSlotStatus;
  priority?: number;
  target_user_type?: number;
  target_min_member_level?: number;
  target_extra?: Record<string, unknown> | null;
  max_show_per_user?: number;
  max_show_per_day_per_user?: number;
  close_dismiss_count?: number;
  can_close?: boolean;
  extra?: Record<string, unknown> | null;
}

/** 更新运营位参数 */
export interface UpdateSlotParam {
  name?: string;
  slot_type?: CmsSlotType;
  scene?: string;
  title?: string | null;
  subtitle?: string | null;
  image_url?: string | null;
  detail?: string | null;
  jump_type?: CmsJumpType;
  jump_target?: string | null;
  jump_extra?: Record<string, unknown> | null;
  start_time?: string | null;
  end_time?: string | null;
  status?: CmsSlotStatus;
  priority?: number;
  target_user_type?: number;
  target_min_member_level?: number;
  target_extra?: Record<string, unknown> | null;
  max_show_per_user?: number;
  max_show_per_day_per_user?: number;
  close_dismiss_count?: number;
  can_close?: boolean;
  extra?: Record<string, unknown> | null;
}

/** 运营位详情(管理端) */
export interface GetSlotDetail {
  id: number;
  code: string;
  name: string;
  slot_type: CmsSlotType;
  scene: string;
  title?: string | null;
  subtitle?: string | null;
  image_url?: string | null;
  detail?: string | null;
  jump_type: CmsJumpType;
  jump_target?: string | null;
  jump_extra?: Record<string, unknown> | null;
  start_time?: string | null;
  end_time?: string | null;
  status: CmsSlotStatus;
  priority: number;
  target_user_type: number;
  target_min_member_level: number;
  target_extra?: Record<string, unknown> | null;
  max_show_per_user: number;
  max_show_per_day_per_user: number;
  close_dismiss_count: number;
  can_close: boolean;
  extra?: Record<string, unknown> | null;
  created_by: number;
  updated_by?: number | null;
  created_time: string;
  updated_time?: string | null;
}

/** 命中的运营位(用户端简化输出) */
export interface GetActiveSlot {
  id: number;
  code: string;
  slot_type: CmsSlotType;
  scene: string;
  title?: string | null;
  subtitle?: string | null;
  image_url?: string | null;
  detail?: string | null;
  jump_type: CmsJumpType;
  jump_target?: string | null;
  jump_extra?: Record<string, unknown> | null;
  can_close: boolean;
  priority: number;
  extra?: Record<string, unknown> | null;
}

/** 运营位列表查询参数(管理端) */
export interface SlotListParams extends PaginationParams {
  status?: CmsSlotStatus;
  slot_type?: CmsSlotType;
  scene?: string;
  keyword?: string;
}

/** 上报运营位行为参数 */
export interface ReportSlotActionParam {
  action: CmsSlotAction;
  scene?: string | null;
}

/** 运营位统计结果 */
export interface SlotStatsResult {
  show_count: number;
  click_count: number;
  close_count: number;
  ctr: number;
}

/** 受影响行数返回结构 */
export interface CmsSlotUpdatedResult {
  updated: number;
}

/** 删除返回结构 */
export interface CmsSlotDeletedResult {
  deleted: number;
}

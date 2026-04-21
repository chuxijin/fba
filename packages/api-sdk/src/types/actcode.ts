import type { AdminLoginToken } from './admin';

export interface ActcodeOrderPayload {
  order_input: string;
}

export interface ActcodeOrderVerifyResult {
  valid: boolean;
  order_no?: string | null;
  is_bound: boolean;
  can_login: boolean;
  username?: string | null;
  membership_plan_id?: number | null;
  message: string;
}

export interface ActcodeOrderActivateResult {
  order_no: string;
  user_id: number;
  username: string;
  just_activated: boolean;
  membership_plan_id?: number | null;
  tier_code?: string | null;
  tier_name?: string | null;
  membership_valid_to?: string | null;
  message: string;
}

export interface ActcodeOrderLoginResult extends AdminLoginToken {
  order_no: string;
  auto_created: boolean;
  just_activated: boolean;
  membership_plan_id?: number | null;
  tier_code?: string | null;
  tier_name?: string | null;
  membership_valid_to?: string | null;
}

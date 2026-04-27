export interface MembershipBrief {
  family_code: string;
  tier_id: number;
  tier_code: string;
  tier_name: string;
  tier_grade: number;
  tier_weight: number;
  exp: number;
  available_exp: number;
  valid_from: string | null;
  valid_to: string | null;
  status: number;
}

export interface MembershipProgress {
  family_code: string;
  tier_id: number | null;
  tier_grade: number | null;
  exp: number;
  available_exp: number;
  next_exp_required: number | null;
}

export interface MembershipTierBrief {
  id: number;
  family_code: string;
  code: string;
  name: string;
  grade: number;
  exp_required: number;
  weight: number;
  is_default: boolean;
}

export interface MembershipPlanBrief {
  id: number;
  name: string;
  tier_id: number;
  duration_days: number;
  price: number;
  original_price: number;
  description: string | null;
}

export interface MembershipRecordBrief {
  family_code: string;
  tier_id: number;
  plan_id: number | null;
  op_type: string;
  days: number;
  exp_delta: number;
  source: string;
  source_key: string;
  valid_to_after: string | null;
  created_time: string;
}

export interface MembershipRecordListParams {
  page?: number;
  size?: number;
  family_code?: string;
  plan_id?: number;
  tier_id?: number;
}

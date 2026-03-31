export interface MembershipBrief {
  family_code: string;
  tier_id: number;
  tier_code: string;
  tier_name: string;
  tier_grade: number;
  tier_weight: number;
  exp: number;
  valid_from: string | null;
  valid_to: string | null;
  status: number;
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

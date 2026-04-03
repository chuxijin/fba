export type QbankEntity = Record<string, unknown>;

export interface QbankUserAccountDetail extends QbankEntity {
  id: number | string;
  username: string;
  nickname?: string;
  avatar?: string;
  phone?: string;
  email?: string;
  dept?: string | null;
  roles?: string[];
  role_expiries?: QbankRoleExpiry[];
  open_id?: string;
  status?: number;
}

export interface QbankRoleExpiry {
  role_id: number;
  role_name: string;
  valid_from?: string | null;
  valid_to?: string | null;
  status: number;
}

export interface QbankWxLoginParam {
  code: string;
  platform: string;
  nickname?: string;
  avatar?: string;
  encrypted_data?: string;
  iv?: string;
}

export interface QbankWxLoginResponse {
  access_token: string;
  access_token_expire_time?: string;
  session_uuid?: string;
  user?: QbankUserAccountDetail;
  user_info?: QbankUserAccountDetail;
}

export interface QbankCheckInParam {
  practice_count: number;
  practice_duration: number;
}

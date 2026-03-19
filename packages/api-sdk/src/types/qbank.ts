export type QbankEntity = Record<string, unknown>;

export interface QbankUserAccountDetail extends QbankEntity {
  id: number | string;
  username: string;
  nickname?: string;
  avatar?: string;
  phone?: string;
  open_id?: string;
  status?: number;
}

export interface QbankWxLoginParam {
  code: string;
  platform: string;
  nickname?: string;
  avatar?: string;
  encrypted_data?: string;
  iv?: string;
}

export interface QbankTestLoginParam {
  username: string;
  nickname?: string;
}

export interface QbankWxLoginResponse {
  access_token: string;
  user_info: QbankUserAccountDetail;
}

export interface QbankCheckInParam {
  practice_count: number;
  practice_duration: number;
}

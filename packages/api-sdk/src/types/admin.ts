import type { PaginationParams } from './common';

export type AdminEntity = Record<string, unknown>;

export interface AdminListParams extends PaginationParams {
  [key: string]: unknown;
}

export interface AdminCaptchaResult {
  is_enabled: boolean;
  expire_seconds: number;
  uuid: string;
  image: string;
}

export interface AdminLoginParams {
  username: string;
  password: string;
  captcha?: string;
  uuid?: string;
}

export interface AdminUserInfo extends AdminEntity {
  dept_id: number | null;
  username: string;
  nickname: string;
  avatar?: string | null;
  email?: string | null;
  phone?: string | null;
  id: number;
  uuid: string;
  status: number;
  is_superuser: boolean;
  is_staff: boolean;
  is_multi_login: boolean;
  join_time: string;
  last_login_time?: string | null;
}

export interface AdminRoleExpiry {
  role_id: number;
  role_name: string;
  valid_from?: string | null;
  valid_to?: string | null;
  status: number;
}

export interface AdminCurrentUser extends AdminUserInfo {
  dept?: string | null;
  roles: string[];
  role_expiries?: AdminRoleExpiry[];
}

export interface AdminLoginToken extends AdminEntity {
  access_token: string;
  access_token_expire_time: string;
  session_uuid: string;
  password_expire_days_remaining?: number | null;
  user: AdminUserInfo;
}

export interface AdminRefreshTokenResult extends AdminEntity {
  access_token: string;
  access_token_expire_time: string;
  session_uuid: string;
}

export interface AdminSwaggerToken extends AdminEntity {
  access_token: string;
  token_type: string;
  user: AdminUserInfo;
}

export interface CategorySchemaBase {
  app_code: string;
  type?: string;
  name: string;
  code?: string | null;
  description?: string | null;
  parent_id?: number | null;
  icon?: string | null;
  color?: string | null;
  sort_order?: number;
  status?: boolean;
  is_system?: boolean;
  remark?: string | null;
  extra_data?: Record<string, unknown> | null;
}

export interface CreateCategoryParam extends CategorySchemaBase {}

export interface UpdateCategoryParam {
  name?: string | null;
  code?: string | null;
  description?: string | null;
  parent_id?: number | null;
  icon?: string | null;
  color?: string | null;
  sort_order?: number | null;
  status?: boolean | null;
  is_system?: boolean | null;
  remark?: string | null;
  extra_data?: Record<string, unknown> | null;
}

export interface DeleteCategoryParam {
  ids: number[];
}

export interface GetCategoryDetail extends CategorySchemaBase {
  id: number;
  level: number;
  path?: string | null;
  created_by?: number | null;
  updated_by?: number | null;
  created_time: string;
  updated_time?: string | null;
}

export interface GetCategoryTree extends GetCategoryDetail {
  children?: GetCategoryTree[] | null;
}

export interface CategoryListParams extends PaginationParams {
  app_code?: string;
  type?: string;
  name?: string;
  status?: boolean;
}

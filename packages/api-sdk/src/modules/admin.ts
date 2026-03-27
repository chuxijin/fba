import type { ApiClient, FormDataLike } from '../client/types';
import type {
  AdminCaptchaResult,
  AdminCurrentUser,
  AdminEntity,
  AdminListParams,
  AdminLoginParams,
  AdminLoginToken,
  AdminRefreshTokenResult,
  AdminSwaggerToken,
  CategoryListParams,
  CreateCategoryParam,
  CreateFeedbackParam,
  FeedbackListParams,
  GetCategoryDetail,
  GetCategoryTree,
  GetFeedbackDetail,
  UpdateCategoryParam,
  UpdateFeedbackParam,
} from '../types/admin';
import type { PageData } from '../types/common';
import { createScopedClient, type ScopedApiClient } from './_shared';

export interface AdminModule {
  request: ScopedApiClient;
  auth: {
    getCaptcha(): Promise<AdminCaptchaResult>;
    login(data: AdminLoginParams): Promise<AdminLoginToken>;
    refresh(): Promise<AdminRefreshTokenResult>;
    logout(): Promise<void>;
    getCodes(): Promise<string[]>;
    loginSwagger(headers?: Record<string, string>): Promise<AdminSwaggerToken>;
  };
  feedback: {
    create(data: CreateFeedbackParam): Promise<void>;
  };
  sys: {
    user: {
      getMe(): Promise<AdminCurrentUser>;
      getDetail(id: number): Promise<AdminEntity>;
      getRoles(id: number): Promise<AdminEntity[]>;
      getList(params?: AdminListParams): Promise<PageData<AdminEntity>>;
      create(data: AdminEntity): Promise<AdminEntity>;
      update(id: number, data: AdminEntity): Promise<void>;
      updatePermissions(id: number, type: string): Promise<void>;
      updateMyPassword(data: AdminEntity): Promise<void>;
      resetPassword(id: number, password: string): Promise<void>;
      updateMyNickname(nickname: string): Promise<void>;
      updateMyAvatar(avatar: string): Promise<void>;
      updateMyEmail(email: string, captcha: string): Promise<void>;
      remove(id: number): Promise<void>;
    };
    file: {
      upload(data: FormDataLike, folder?: string): Promise<AdminEntity>;
      getList(params?: AdminListParams): Promise<AdminEntity>;
      remove(filename: string): Promise<void>;
      createFolder(folderName: string, parentFolder?: string): Promise<AdminEntity>;
    };
    category: {
      getTree(params?: CategoryListParams): Promise<GetCategoryTree[]>;
      getList(params?: CategoryListParams): Promise<PageData<GetCategoryDetail>>;
      getTypes(appCode: string): Promise<string[]>;
      getAppCodes(): Promise<string[]>;
      getTypeOptions(appCode?: string): Promise<string[]>;
      getDetail(id: number): Promise<GetCategoryDetail>;
      create(data: CreateCategoryParam): Promise<void>;
      update(id: number, data: UpdateCategoryParam): Promise<void>;
      remove(ids: number[]): Promise<void>;
    };
    feedback: {
      getList(params?: FeedbackListParams): Promise<PageData<GetFeedbackDetail>>;
      getDetail(id: number): Promise<GetFeedbackDetail>;
      update(id: number, data: UpdateFeedbackParam): Promise<void>;
      remove(ids: number[]): Promise<void>;
    };
  };
}

export function createAdminModule(client: ApiClient): AdminModule {
  const request = createScopedClient(client, '');

  return {
    request,
    auth: {
      getCaptcha() { return request.get<AdminCaptchaResult>('/auth/captcha'); },
      login(data) { return request.post<AdminLoginToken>('/auth/login', data); },
      refresh() { return request.post<AdminRefreshTokenResult>('/auth/refresh'); },
      logout() { return request.post('/auth/logout'); },
      getCodes() { return request.get<string[]>('/auth/codes'); },
      loginSwagger(headers) {
        return request.raw<AdminSwaggerToken>({ method: 'POST', url: '/auth/login/swagger', headers });
      },
    },
    feedback: {
      create(data) { return request.post('/feedbacks', data); },
    },
    sys: {
      user: {
        getMe() { return request.get<AdminCurrentUser>('/sys/users/me'); },
        getDetail(id) { return request.get<AdminEntity>(`/sys/users/${id}`); },
        getRoles(id) { return request.get<AdminEntity[]>(`/sys/users/${id}/roles`); },
        getList(params) {
          return request.get<PageData<AdminEntity>>('/sys/users', {
            params: params as Record<string, unknown>,
          });
        },
        create(data) { return request.post<AdminEntity>('/sys/users', data); },
        update(id, data) { return request.put(`/sys/users/${id}`, data); },
        updatePermissions(id, type) {
          return request.put(`/sys/users/${id}/permissions`, undefined, { params: { type } });
        },
        updateMyPassword(data) { return request.put('/sys/users/me/password', data); },
        resetPassword(id, password) { return request.put(`/sys/users/${id}/password`, { password }); },
        updateMyNickname(nickname) { return request.put('/sys/users/me/nickname', { nickname }); },
        updateMyAvatar(avatar) { return request.put('/sys/users/me/avatar', { avatar }); },
        updateMyEmail(email, captcha) { return request.put('/sys/users/me/email', { email, captcha }); },
        remove(id) { return request.delete(`/sys/users/${id}`); },
      },
      file: {
        upload(data, folder) {
          return request.post<AdminEntity>('/sys/files/upload', data, {
            params: folder ? { folder } : undefined,
          });
        },
        getList(params) {
          return request.get<AdminEntity>('/sys/files/list', {
            params: params as Record<string, unknown>,
          });
        },
        remove(filename) {
          return request.delete('/sys/files/delete', undefined, {
            params: { filename },
          });
        },
        createFolder(folderName, parentFolder) {
          return request.post<AdminEntity>('/sys/files/create-folder', undefined, {
            params: { folder_name: folderName, parent_folder: parentFolder },
          });
        },
      },
      category: {
        getTree(params) {
          return request.get<GetCategoryTree[]>('/sys/categories/tree', {
            params: params as Record<string, unknown>,
          });
        },
        getList(params) {
          return request.get<PageData<GetCategoryDetail>>('/sys/category', {
            params: params as Record<string, unknown>,
          });
        },
        getTypes(appCode) { return request.get<string[]>(`/sys/category/types/${appCode}`); },
        getAppCodes() { return request.get<string[]>('/sys/category/options/app-codes'); },
        getTypeOptions(appCode) {
          return request.get<string[]>('/sys/category/options/types', {
            params: appCode ? { app_code: appCode } : undefined,
          });
        },
        getDetail(id) { return request.get<GetCategoryDetail>(`/sys/category/${id}`); },
        create(data) { return request.post('/sys/category', data); },
        update(id, data) { return request.put(`/sys/category/${id}`, data); },
        remove(ids) { return request.delete('/sys/category', { ids }); },
      },
      feedback: {
        getList(params) {
          return request.get<PageData<GetFeedbackDetail>>('/sys/feedbacks', {
            params: params as Record<string, unknown>,
          });
        },
        getDetail(id) { return request.get<GetFeedbackDetail>(`/sys/feedbacks/${id}`); },
        update(id, data) { return request.put(`/sys/feedbacks/${id}`, data); },
        remove(ids) { return request.delete('/sys/feedbacks', { ids }); },
      },
    },
  };
}

import type { ApiClient, FormDataLike } from '../client/types';
import type { PageData } from '../types/common';
import type {
  GkContentParams,
  GkContentResult,
  GkCiyuParams,
  GkCiyuResult,
  GkGangweiParams,
  GkGangweiResult,
  GkGuanmeiParams,
  GkGuanmeiResult,
  GkMaterialParams,
  GkMaterialResult,
  GkQuestionAnswerResult,
  GkQuestionOptionResult,
  GkQuestionParams,
  GkQuestionResult,
  GkShipingParams,
  GkShipingResult,
  GkShizhenParams,
  GkShizhenResult,
  GongkaoEntity,
  GongkaoListParams,
} from '../types/gongkao';
import { createScopedClient, type ScopedApiClient } from './_shared';

export interface GongkaoModule {
  request: ScopedApiClient;
  ciyu: {
    getHot(limit?: number): Promise<GkCiyuResult[]>;
    getDetail(id: number): Promise<GkCiyuResult>;
    getList(params?: GkCiyuParams): Promise<PageData<GkCiyuResult>>;
    create(data: GongkaoEntity): Promise<void>;
    update(id: number, data: GongkaoEntity): Promise<void>;
    remove(ids: number[]): Promise<void>;
    incrementView(id: number): Promise<void>;
  };
  shizhen: {
    getDetail(id: number): Promise<GkShizhenResult>;
    getList(params?: GkShizhenParams): Promise<PageData<GkShizhenResult>>;
    create(data: GongkaoEntity): Promise<void>;
    update(id: number, data: GongkaoEntity): Promise<void>;
    remove(ids: number[]): Promise<void>;
  };
  guanmei: {
    getDetail(id: number): Promise<GkGuanmeiResult>;
    getList(params?: GkGuanmeiParams): Promise<PageData<GkGuanmeiResult>>;
    create(data: GongkaoEntity): Promise<void>;
    update(id: number, data: GongkaoEntity): Promise<void>;
    remove(ids: number[]): Promise<void>;
    incrementView(id: number): Promise<void>;
  };
  shiping: {
    getDetail(id: number): Promise<GkShipingResult>;
    getList(params?: GkShipingParams): Promise<PageData<GkShipingResult>>;
    create(data: GongkaoEntity): Promise<void>;
    update(id: number, data: GongkaoEntity): Promise<void>;
    remove(ids: number[]): Promise<void>;
    incrementView(id: number): Promise<void>;
    exportPdf<T = unknown>(id: number): Promise<T>;
  };
  zhenti: {
    question: {
      getDetail(id: number): Promise<GkQuestionResult>;
      getList(params?: GkQuestionParams): Promise<PageData<GkQuestionResult>>;
      getHotSources(limit?: number): Promise<string[]>;
      create(data: GongkaoEntity): Promise<void>;
      update(id: number, data: GongkaoEntity): Promise<void>;
      remove(ids: number[]): Promise<void>;
    };
    option: {
      getDetail(id: number): Promise<GkQuestionOptionResult>;
      getByQuestion(questionId: number): Promise<GkQuestionOptionResult[]>;
      create(data: GongkaoEntity): Promise<void>;
      update(id: number, data: GongkaoEntity): Promise<void>;
      remove(ids: number[]): Promise<void>;
    };
    answer: {
      getDetail(id: number): Promise<GkQuestionAnswerResult>;
      getByQuestion(questionId: number): Promise<GkQuestionAnswerResult[]>;
      getOfficial(questionId: number): Promise<GkQuestionAnswerResult | null>;
      create(data: GongkaoEntity): Promise<void>;
      update(id: number, data: GongkaoEntity): Promise<void>;
      remove(ids: number[]): Promise<void>;
    };
    material: {
      getDetail(id: number): Promise<GkMaterialResult>;
      getList(params?: GkMaterialParams): Promise<PageData<GkMaterialResult>>;
      create(data: GongkaoEntity): Promise<void>;
      update(id: number, data: GongkaoEntity): Promise<void>;
      remove(ids: number[]): Promise<void>;
    };
  };
  content: {
    getTags(limit?: number): Promise<string[]>;
    getDetail(id: number): Promise<GkContentResult>;
    getBySlug(slug: string): Promise<GkContentResult>;
    getList(params?: GkContentParams): Promise<PageData<GkContentResult>>;
    create(data: GongkaoEntity): Promise<void>;
    update(id: number, data: GongkaoEntity): Promise<void>;
    remove(ids: number[]): Promise<void>;
    incrementView(id: number): Promise<void>;
  };
  gangwei: {
    getDetail(id: number): Promise<GkGangweiResult>;
    getList(params?: GkGangweiParams): Promise<PageData<GkGangweiResult> | { items: GkGangweiResult[]; total: number; page: number; size: number }>;
    create(data: GongkaoEntity): Promise<void>;
    update(id: number, data: GongkaoEntity): Promise<void>;
    remove(ids: number[]): Promise<void>;
    parseImportFile(data: FormDataLike): Promise<GongkaoEntity>;
    reparseImportFile(fileKey: string, headerRow?: number): Promise<GongkaoEntity>;
    executeImport(data: GongkaoEntity): Promise<GongkaoEntity>;
    parseScoreImportFile(data: FormDataLike): Promise<GongkaoEntity>;
    reparseScoreImportFile(fileKey: string, headerRow?: number): Promise<GongkaoEntity>;
    executeScoreImport(data: GongkaoEntity): Promise<GongkaoEntity>;
  };
  gangweiMatch: { canApply(gangweiId: number): Promise<GongkaoEntity>; };
  jingyan: {
    getDetail(id: number): Promise<GongkaoEntity>;
    getList(params?: GongkaoListParams): Promise<PageData<GongkaoEntity>>;
    create(data: GongkaoEntity): Promise<void>;
    update(id: number, data: GongkaoEntity): Promise<void>;
    remove(ids: number[]): Promise<void>;
    incrementView(id: number): Promise<void>;
  };
  userProfile: {
    getMe(): Promise<GongkaoEntity | null>;
    createMe(data: GongkaoEntity): Promise<GongkaoEntity>;
    updateMe(data: GongkaoEntity): Promise<void>;
    saveMe(data: GongkaoEntity): Promise<GongkaoEntity>;
    removeMe(): Promise<void>;
  };
  dictRegion: {
    getTree(): Promise<GongkaoEntity[]>;
    getProvinces(): Promise<GongkaoEntity[]>;
    getChildren(parentCode?: string): Promise<GongkaoEntity[]>;
    getDetail(id: number): Promise<GongkaoEntity>;
    getByCode(code: string): Promise<GongkaoEntity>;
    getList(params?: GongkaoListParams): Promise<PageData<GongkaoEntity>>;
    create(data: GongkaoEntity): Promise<void>;
    update(id: number, data: GongkaoEntity): Promise<void>;
    remove(id: number): Promise<void>;
  };
  dictMajor: {
    getTree(): Promise<GongkaoEntity[]>;
    getRootList(): Promise<GongkaoEntity[]>;
    getChildren(parentCode?: string): Promise<GongkaoEntity[]>;
    getDetail(id: number): Promise<GongkaoEntity>;
    getByCode(code: string): Promise<GongkaoEntity>;
    getByName(name: string): Promise<GongkaoEntity[]>;
    getList(params?: GongkaoListParams): Promise<PageData<GongkaoEntity>>;
    create(data: GongkaoEntity): Promise<void>;
    update(id: number, data: GongkaoEntity): Promise<void>;
    remove(id: number): Promise<void>;
  };
}

export function createGongkaoModule(client: ApiClient): GongkaoModule {
  const request = createScopedClient(client, '/gk');
  return {
    request,
    ciyu: {
      getHot(limit = 10) { return request.get<GkCiyuResult[]>('/ciyu/hot', { params: { limit } }); },
      getDetail(id) { return request.get<GkCiyuResult>(`/ciyu/${id}`); },
      getList(params) { return request.get<PageData<GkCiyuResult>>('/ciyu', { params: params as Record<string, unknown> }); },
      create(data) { return request.post('/ciyu', data); },
      update(id, data) { return request.put(`/ciyu/${id}`, data); },
      remove(ids) { return request.delete('/ciyu', { ids }); },
      incrementView(id) { return request.post(`/ciyu/${id}/view`); },
    },
    shizhen: {
      getDetail(id) { return request.get<GkShizhenResult>(`/shizhen/${id}`); },
      getList(params) { return request.get<PageData<GkShizhenResult>>('/shizhen', { params: params as Record<string, unknown> }); },
      create(data) { return request.post('/shizhen', data); },
      update(id, data) { return request.put(`/shizhen/${id}`, data); },
      remove(ids) { return request.delete('/shizhen', { ids }); },
    },
    guanmei: {
      getDetail(id) { return request.get<GkGuanmeiResult>(`/guanmei/${id}`); },
      getList(params) { return request.get<PageData<GkGuanmeiResult>>('/guanmei', { params: params as Record<string, unknown> }); },
      create(data) { return request.post('/guanmei', data); },
      update(id, data) { return request.put(`/guanmei/${id}`, data); },
      remove(ids) { return request.delete('/guanmei', { ids }); },
      incrementView(id) { return request.post(`/guanmei/${id}/view`); },
    },
    shiping: {
      getDetail(id) { return request.get<GkShipingResult>(`/shiping/${id}`); },
      getList(params) { return request.get<PageData<GkShipingResult>>('/shiping', { params: params as Record<string, unknown> }); },
      create(data) { return request.post('/shiping', data); },
      update(id, data) { return request.put(`/shiping/${id}`, data); },
      remove(ids) { return request.delete('/shiping', { ids }); },
      incrementView(id) { return request.post(`/shiping/${id}/view`); },
      exportPdf(id) { return request.raw({ method: 'GET', url: `/shiping/${id}/pdf` }); },
    },
    zhenti: {
      question: {
        getDetail(id) { return request.get<GkQuestionResult>(`/zhenti/question/${id}`); },
        getList(params) { return request.get<PageData<GkQuestionResult>>('/zhenti/question', { params: params as Record<string, unknown> }); },
        getHotSources(limit = 10) { return request.get<string[]>('/zhenti/question/source/hot', { params: { limit } }); },
        create(data) { return request.post('/zhenti/question', data); },
        update(id, data) { return request.put(`/zhenti/question/${id}`, data); },
        remove(ids) { return request.delete('/zhenti/question', { ids }); },
      },
      option: {
        getDetail(id) { return request.get<GkQuestionOptionResult>(`/zhenti/option/${id}`); },
        getByQuestion(questionId) { return request.get<GkQuestionOptionResult[]>(`/zhenti/option/question/${questionId}`); },
        create(data) { return request.post('/zhenti/option', data); },
        update(id, data) { return request.put(`/zhenti/option/${id}`, data); },
        remove(ids) { return request.delete('/zhenti/option', { ids }); },
      },
      answer: {
        getDetail(id) { return request.get<GkQuestionAnswerResult>(`/zhenti/answer/${id}`); },
        getByQuestion(questionId) { return request.get<GkQuestionAnswerResult[]>(`/zhenti/answer/question/${questionId}`); },
        getOfficial(questionId) { return request.get<GkQuestionAnswerResult | null>(`/zhenti/answer/question/${questionId}/official`); },
        create(data) { return request.post('/zhenti/answer', data); },
        update(id, data) { return request.put(`/zhenti/answer/${id}`, data); },
        remove(ids) { return request.delete('/zhenti/answer', { ids }); },
      },
      material: {
        getDetail(id) { return request.get<GkMaterialResult>(`/zhenti/material/${id}`); },
        getList(params) { return request.get<PageData<GkMaterialResult>>('/zhenti/material', { params: params as Record<string, unknown> }); },
        create(data) { return request.post('/zhenti/material', data); },
        update(id, data) { return request.put(`/zhenti/material/${id}`, data); },
        remove(ids) { return request.delete('/zhenti/material', { ids }); },
      },
    },
    content: {
      getTags(limit = 50) { return request.get<string[]>('/content/tags', { params: { limit } }); },
      getDetail(id) { return request.get<GkContentResult>(`/content/${id}`); },
      getBySlug(slug) { return request.get<GkContentResult>(`/content/slug/${slug}`); },
      getList(params) { return request.get<PageData<GkContentResult>>('/content', { params: params as Record<string, unknown> }); },
      create(data) { return request.post('/content', data); },
      update(id, data) { return request.put(`/content/${id}`, data); },
      remove(ids) { return request.delete('/content', { ids }); },
      incrementView(id) { return request.post(`/content/${id}/view`); },
    },
    gangwei: {
      getDetail(id) { return request.get<GkGangweiResult>(`/gangwei/${id}`); },
      getList(params) { return request.get<PageData<GkGangweiResult> | { items: GkGangweiResult[]; total: number; page: number; size: number }>('/gangwei', { params: params as Record<string, unknown> }); },
      create(data) { return request.post('/gangwei', data); },
      update(id, data) { return request.put(`/gangwei/${id}`, data); },
      remove(ids) { return request.delete('/gangwei', { ids }); },
      parseImportFile(data) { return request.post<GongkaoEntity>('/gangwei/import/parse', data); },
      reparseImportFile(fileKey, headerRow = 0) { return request.post<GongkaoEntity>('/gangwei/import/reparse', undefined, { params: { file_key: fileKey, header_row: headerRow } }); },
      executeImport(data) { return request.post<GongkaoEntity>('/gangwei/import/execute', data); },
      parseScoreImportFile(data) { return request.post<GongkaoEntity>('/gangwei/score/import/parse', data); },
      reparseScoreImportFile(fileKey, headerRow = 0) { return request.post<GongkaoEntity>('/gangwei/score/import/reparse', undefined, { params: { file_key: fileKey, header_row: headerRow } }); },
      executeScoreImport(data) { return request.post<GongkaoEntity>('/gangwei/score/import/execute', data); },
    },
    gangweiMatch: { canApply(gangweiId) { return request.get<GongkaoEntity>(`/gangwei/${gangweiId}/can-apply`); } },
    jingyan: {
      getDetail(id) { return request.get<GongkaoEntity>(`/jingyan/${id}`); },
      getList(params) { return request.get<PageData<GongkaoEntity>>('/jingyan', { params: params as Record<string, unknown> }); },
      create(data) { return request.post('/jingyan', data); },
      update(id, data) { return request.put(`/jingyan/${id}`, data); },
      remove(ids) { return request.delete('/jingyan', { ids }); },
      incrementView(id) { return request.post(`/jingyan/${id}/view`); },
    },
    userProfile: {
      getMe() { return request.get<GongkaoEntity | null>('/profile/me'); },
      createMe(data) { return request.post<GongkaoEntity>('/profile/me', data); },
      updateMe(data) { return request.put('/profile/me', data); },
      saveMe(data) { return request.post<GongkaoEntity>('/profile/me/save', data); },
      removeMe() { return request.delete('/profile/me'); },
    },
    dictRegion: {
      getTree() { return request.get<GongkaoEntity[]>('/dict/region/tree'); },
      getProvinces() { return request.get<GongkaoEntity[]>('/dict/region/provinces'); },
      getChildren(parentCode) { return request.get<GongkaoEntity[]>('/dict/region/children', { params: parentCode ? { parent_code: parentCode } : undefined }); },
      getDetail(id) { return request.get<GongkaoEntity>(`/dict/region/${id}`); },
      getByCode(code) { return request.get<GongkaoEntity>(`/dict/region/code/${code}`); },
      getList(params) { return request.get<PageData<GongkaoEntity>>('/dict/region', { params: params as Record<string, unknown> }); },
      create(data) { return request.post('/dict/region', data); },
      update(id, data) { return request.put(`/dict/region/${id}`, data); },
      remove(id) { return request.delete(`/dict/region/${id}`); },
    },
    dictMajor: {
      getTree() { return request.get<GongkaoEntity[]>('/dict/major/tree'); },
      getRootList() { return request.get<GongkaoEntity[]>('/dict/major/root'); },
      getChildren(parentCode) { return request.get<GongkaoEntity[]>('/dict/major/children', { params: parentCode ? { parent_code: parentCode } : undefined }); },
      getDetail(id) { return request.get<GongkaoEntity>(`/dict/major/${id}`); },
      getByCode(code) { return request.get<GongkaoEntity>(`/dict/major/code/${code}`); },
      getByName(name) { return request.get<GongkaoEntity[]>('/dict/major/search', { params: { name } }); },
      getList(params) { return request.get<PageData<GongkaoEntity>>('/dict/major', { params: params as Record<string, unknown> }); },
      create(data) { return request.post('/dict/major', data); },
      update(id, data) { return request.put(`/dict/major/${id}`, data); },
      remove(id) { return request.delete(`/dict/major/${id}`); },
    },
  };
}





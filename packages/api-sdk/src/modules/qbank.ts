import type { ApiClient, FormDataLike } from '../client/types';
import { createBankModule, type BankModule } from './bank';
import { createMaterialModule, type MaterialModule } from './material';
import { createPracticeModule, type PracticeModule } from './practice';
import { createQuestionModule, type QuestionModule } from './question';
import { createScopedClient, type ScopedApiClient } from './_shared';
import type { PageData } from '../types/common';
import type { QbankCheckInParam, QbankEntity, QbankUserAccountDetail, QbankWxLoginParam, QbankWxLoginResponse } from '../types/qbank';
import type {
  BatchUpsertPracticeRecordsParam,
  CreatePracticeSessionParam,
  GetPracticeRecordDetail,
  GetPracticeRecordListItem,
  GetPracticeSessionDetail,
  GetPracticeSessionListItem,
  LatestPracticeSessionQuery,
  PracticeSessionQueryParam,
  SessionReport,
  SubmitPracticeSessionParam,
  SubmitPracticeSessionResult,
} from '../types/practice';

export interface QbankModule {
  request: ScopedApiClient;
  bank: BankModule;
  material: MaterialModule;
  question: QuestionModule;
  practice: PracticeModule;
  auth: {
    wxLogin(data: QbankWxLoginParam): Promise<QbankWxLoginResponse>;
    getMe(): Promise<QbankUserAccountDetail>;
  };
  home: {
    getDashboard(): Promise<QbankEntity>;
    checkIn(data: QbankCheckInParam): Promise<void>;
    getCheckInCalendar(year?: number, month?: number): Promise<QbankEntity>;
    getRank(rankType?: string, limit?: number): Promise<QbankEntity>;
  };
  chapter: {
    getDetail(id: number): Promise<QbankEntity>;
    getCustomerTree(bankId: number): Promise<QbankEntity[]>;
    getTree(bankId: number): Promise<QbankEntity[]>;
    create(data: QbankEntity): Promise<void>;
    update(id: number, data: QbankEntity): Promise<void>;
    remove(ids: number[]): Promise<void>;
  };
  session: {
    create(data: CreatePracticeSessionParam): Promise<GetPracticeSessionDetail>;
    getLatest(params?: LatestPracticeSessionQuery): Promise<GetPracticeSessionDetail | null>;
    getList(params?: PracticeSessionQueryParam): Promise<PageData<GetPracticeSessionListItem>>;
    getDetail(id: number): Promise<GetPracticeSessionDetail>;
    submit(id: number, data: SubmitPracticeSessionParam): Promise<SubmitPracticeSessionResult>;
    abandon(id: number): Promise<void>;
    remove(id: number): Promise<void>;
    upsertRecords(id: number, data: BatchUpsertPracticeRecordsParam): Promise<QbankEntity>;
    getRecord(id: number): Promise<GetPracticeRecordDetail>;
    getRecords(params?: { session_id?: number; question_id?: number }): Promise<PageData<GetPracticeRecordListItem>>;
    getSessionRecords(id: number): Promise<GetPracticeRecordDetail[]>;
    getReport(id: number): Promise<SessionReport>;
    getSolution(id: number): Promise<unknown>;
  };
  favorite: {
    create(data: QbankEntity): Promise<void>;
    getList(params?: QbankEntity): Promise<QbankEntity>;
    removeByQuestion(questionId: number): Promise<void>;
    getFolders(): Promise<QbankEntity[]>;
    clearFolder(data: QbankEntity): Promise<void>;
    check(data: QbankEntity): Promise<QbankEntity>;
    getStatistics(groupBy?: string): Promise<QbankEntity>;
    getGrouped(groupBy?: string): Promise<QbankEntity[]>;
    getIds(params?: QbankEntity): Promise<number[]>;
    getDetail(id: number): Promise<QbankEntity>;
    update(id: number, data: QbankEntity): Promise<void>;
    pin(id: number, data: QbankEntity): Promise<void>;
    remove(data: QbankEntity): Promise<void>;
  };
  note: {
    create(data: QbankEntity): Promise<void>;
    getDetail(id: number): Promise<QbankEntity>;
    getList(params?: QbankEntity): Promise<QbankEntity>;
    getQuestionPublic(questionId: number): Promise<QbankEntity[]>;
    update(id: number, data: QbankEntity): Promise<void>;
    remove(id: number): Promise<void>;
    vote(id: number, data: QbankEntity): Promise<void>;
    unvote(id: number): Promise<void>;
    getMyVote(id: number): Promise<QbankEntity>;
    getVoteStatistics(id: number): Promise<QbankEntity>;
    getStatistics(groupBy?: string): Promise<QbankEntity>;
    getGrouped(groupBy?: string): Promise<QbankEntity[]>;
    getIds(params?: QbankEntity): Promise<number[]>;
  };
  wrongQuestion: {
    getStatistics(groupBy?: string): Promise<QbankEntity>;
    getDetail(id: number): Promise<QbankEntity>;
    getList(params?: QbankEntity): Promise<QbankEntity>;
    pin(id: number, data: QbankEntity): Promise<void>;
    remove(data: QbankEntity): Promise<void>;
    clearMastered(data?: QbankEntity): Promise<void>;
    getGrouped(groupBy?: string): Promise<QbankEntity[]>;
    getIds(params?: QbankEntity): Promise<number[]>;
    answerCorrect(questionId: number, data?: QbankEntity): Promise<QbankEntity>;
  };
  banner: {
    getActiveList(scene?: string): Promise<QbankEntity[]>;
    click(id: number): Promise<void>;
    getAdminList(params?: QbankEntity): Promise<QbankEntity[]>;
    getDetail(id: number): Promise<QbankEntity>;
    create(data: QbankEntity): Promise<void>;
    update(id: number, data: QbankEntity): Promise<void>;
    remove(id: number): Promise<void>;
  };
  notice: {
    getActiveList(scene?: string): Promise<QbankEntity[]>;
    getAdminList(params?: QbankEntity): Promise<QbankEntity[]>;
    getDetail(id: number): Promise<QbankEntity>;
    create(data: QbankEntity): Promise<void>;
    update(id: number, data: QbankEntity): Promise<void>;
    remove(id: number): Promise<void>;
  };
  activation: {
    query(data: QbankEntity): Promise<QbankEntity>;
    redeem(data: QbankEntity): Promise<QbankEntity>;
  };
  settings: {
    getStudyPreference(): Promise<QbankEntity>;
    updateStudyPreference(data: QbankEntity): Promise<void>;
  };
  upload: {
    uploadAvatar(data: FormDataLike): Promise<QbankEntity>;
  };
  parse: {
    parsePdf(data: FormDataLike): Promise<QbankEntity>;
    smartExtract(data: FormDataLike): Promise<QbankEntity>;
    smartExtractStream<T = unknown>(data: FormDataLike): Promise<T>;
    smartCommit(data: QbankEntity): Promise<QbankEntity>;
    saveSegments(data: QbankEntity): Promise<QbankEntity>;
  };
}

export function createQbankModule(client: ApiClient): QbankModule {
  const request = createScopedClient(client, '/qbank');

  return {
    request,
    bank: createBankModule(request),
    material: createMaterialModule(request),
    question: createQuestionModule(request),
    practice: createPracticeModule(request),
    auth: {
      wxLogin(data) { return client.post<QbankWxLoginResponse>('/oauth2/wechat/miniapp/login', data); },
      getMe() { return request.get<QbankUserAccountDetail>('/auth/me'); },
    },
    home: {
      getDashboard() { return request.get<QbankEntity>('/home/dashboard'); },
      checkIn(data) { return request.post('/home/check-in', data); },
      getCheckInCalendar(year, month) { return request.get<QbankEntity>('/home/check-in-calendar', { params: { year, month } }); },
      getRank(rankType = 'practice_count', limit = 100) { return request.get<QbankEntity>('/home/rank', { params: { rank_type: rankType, limit } }); },
    },
    chapter: {
      getDetail(id) { return request.get<QbankEntity>(`/chapters/${id}`); },
      getCustomerTree(bankId) { return request.get<QbankEntity[]>('/chapters/tree/customer', { params: { bank_id: bankId } }); },
      getTree(bankId) { return request.get<QbankEntity[]>('/chapters', { params: { bank_id: bankId } }); },
      create(data) { return request.post('/chapters', data); },
      update(id, data) { return request.put(`/chapters/${id}`, data); },
      remove(ids) { return request.delete('/chapters', { ids }); },
    },
    session: {
      create(data) { return request.post<GetPracticeSessionDetail>('/sessions', data); },
      getLatest(params) { return request.get<GetPracticeSessionDetail | null>('/sessions/latest', { params: params as Record<string, unknown> | undefined }); },
      getList(params) { return request.get<PageData<GetPracticeSessionListItem>>('/sessions', { params: params as Record<string, unknown> }); },
      getDetail(id) { return request.get<GetPracticeSessionDetail>(`/sessions/${id}`); },
      submit(id, data) { return request.post<SubmitPracticeSessionResult>(`/sessions/${id}/submit`, data); },
      abandon(id) { return request.post(`/sessions/${id}/abandon`); },
      remove(id) { return request.delete(`/sessions/${id}`); },
      upsertRecords(id, data) { return request.post<QbankEntity>(`/sessions/${id}/records`, data); },
      getRecord(id) { return request.get<GetPracticeRecordDetail>(`/sessions/records/${id}`); },
      getRecords(params) { return request.get<PageData<GetPracticeRecordListItem>>('/sessions/records', { params: params as Record<string, unknown> | undefined }); },
      getSessionRecords(id) { return request.get<GetPracticeRecordDetail[]>(`/sessions/${id}/records`); },
      getReport(id) { return request.get<SessionReport>(`/sessions/${id}/report`); },
      getSolution(id) { return request.get<unknown>(`/sessions/${id}/solution`); },
    },
    favorite: {
      create(data) { return request.post('/favorites', data); },
      getList(params) { return request.get<QbankEntity>('/favorites', { params: params as Record<string, unknown> }); },
      removeByQuestion(questionId) { return request.delete(`/favorites/questions/${questionId}`); },
      getFolders() { return request.get<QbankEntity[]>('/favorites/folders'); },
      clearFolder(data) { return request.post('/favorites/folders/clear', data); },
      check(data) { return request.post<QbankEntity>('/favorites/questions/check', data); },
      getStatistics(groupBy) { return request.get<QbankEntity>('/favorites/statistics', { params: groupBy ? { group_by: groupBy } : undefined }); },
      getDetail(id) { return request.get<QbankEntity>(`/favorites/${id}`); },
      update(id, data) { return request.put(`/favorites/${id}`, data); },
      pin(id, data) { return request.put(`/favorites/${id}/pin`, data); },
      remove(data) { return request.delete('/favorites', data); },
      getGrouped(groupBy = 'bank') { return request.get<QbankEntity[]>('/favorites/grouped', { params: { group_by: groupBy } }); },
      getIds(params) { return request.get<number[]>('/favorites/ids', { params: params as Record<string, unknown> }); },
    },
    note: {
      create(data) { return request.post('/notes', data); },
      getDetail(id) { return request.get<QbankEntity>(`/notes/${id}`); },
      getList(params) { return request.get<QbankEntity>('/notes', { params: params as Record<string, unknown> }); },
      getQuestionPublic(questionId) { return request.get<QbankEntity[]>(`/notes/questions/${questionId}/public`); },
      update(id, data) { return request.put(`/notes/${id}`, data); },
      remove(id) { return request.delete(`/notes/${id}`); },
      vote(id, data) { return request.post(`/notes/${id}/vote`, data); },
      unvote(id) { return request.delete(`/notes/${id}/vote`); },
      getMyVote(id) { return request.get<QbankEntity>(`/notes/${id}/vote/my`); },
      getVoteStatistics(id) { return request.get<QbankEntity>(`/notes/${id}/vote/statistics`); },
      getStatistics(groupBy) { return request.get<QbankEntity>('/notes/statistics', { params: groupBy ? { group_by: groupBy } : undefined }); },
      getGrouped(groupBy = 'bank') { return request.get<QbankEntity[]>('/notes/grouped', { params: { group_by: groupBy } }); },
      getIds(params) { return request.get<number[]>('/notes/ids', { params: params as Record<string, unknown> }); },
    },
    wrongQuestion: {
      getStatistics(groupBy) { return request.get<QbankEntity>('/wrong-questions/statistics', { params: groupBy ? { group_by: groupBy } : undefined }); },
      getDetail(id) { return request.get<QbankEntity>(`/wrong-questions/${id}`); },
      getList(params) { return request.get<QbankEntity>('/wrong-questions', { params: params as Record<string, unknown> }); },
      pin(id, data) { return request.put(`/wrong-questions/${id}/pin`, data); },
      remove(data) { return request.delete('/wrong-questions', data); },
      clearMastered(data) { return request.post('/wrong-questions/clear-mastered', data); },
      getGrouped(groupBy = 'bank') { return request.get<QbankEntity[]>('/wrong-questions/grouped', { params: { group_by: groupBy } }); },
      getIds(params) { return request.get<number[]>('/wrong-questions/ids', { params: params as Record<string, unknown> }); },
      answerCorrect(questionId, data) { return request.post<QbankEntity>(`/wrong-questions/${questionId}/answer-correct`, data); },
    },
    banner: {
      getActiveList(scene) { return request.get<QbankEntity[]>('/banners', { params: scene ? { scene } : undefined }); },
      click(id) { return request.post(`/banners/${id}/click`); },
      getAdminList(params) { return request.get<QbankEntity[]>('/banners/admin', { params: params as Record<string, unknown> }); },
      getDetail(id) { return request.get<QbankEntity>(`/banners/${id}`); },
      create(data) { return request.post('/banners', data); },
      update(id, data) { return request.put(`/banners/${id}`, data); },
      remove(id) { return request.delete(`/banners/${id}`); },
    },
    notice: {
      getActiveList(scene) { return request.get<QbankEntity[]>('/notices', { params: scene ? { scene } : undefined }); },
      getAdminList(params) { return request.get<QbankEntity[]>('/notices/admin', { params: params as Record<string, unknown> }); },
      getDetail(id) { return request.get<QbankEntity>(`/notices/${id}`); },
      create(data) { return request.post('/notices', data); },
      update(id, data) { return request.put(`/notices/${id}`, data); },
      remove(id) { return request.delete(`/notices/${id}`); },
    },
    activation: {
      query(data) { return request.post<QbankEntity>('/activation/query', data); },
      redeem(data) { return request.post<QbankEntity>('/activation/redeem', data); },
    },
    settings: {
      getStudyPreference() { return request.get<QbankEntity>('/settings/study-preference'); },
      updateStudyPreference(data) { return request.put('/settings/study-preference', data); },
    },
    upload: {
      uploadAvatar(data) { return request.post<QbankEntity>('/upload/avatar', data); },
    },
    parse: {
      parsePdf(data) { return request.post<QbankEntity>('/parse/pdf', data); },
      smartExtract(data) { return request.post<QbankEntity>('/parse/smart-extract', data); },
      smartExtractStream(data) { return request.raw({ method: 'POST', url: '/parse/smart-extract-stream', data }); },
      smartCommit(data) { return request.post<QbankEntity>('/parse/smart-commit', data); },
      saveSegments(data) { return request.post<QbankEntity>('/parse/save-segments', data); },
    },
  };
}

import type { ApiClient } from '../client/types';
import type {
  GetQuestionDetail,
  GetQuestionListItem,
  QuestionAnalysisItem,
  CreatePracticeSessionParam,
  PracticeSessionQueryParam,
  GetPracticeSessionListItem,
  GetPracticeSessionDetail,
  SubmitPracticeSessionParam,
  SubmitPracticeSessionResult,
  BatchUpsertPracticeRecordsParam,
  GetPracticeRecordDetail,
  GetPracticeRecordListItem,
  SessionReport,
  SessionType,
  PageData,
} from '../types';

export interface PracticeModule {
  /** 鑾峰彇缁冑範棰樼洰鍒楄〃锛堟寜绛涢€夋潯浠讹級 */
  getQuestions(params?: {
    bank_id?: number;
    chapter_id?: number;
    type?: string;
    difficulty?: string;
  }): Promise<GetQuestionListItem[]>;

  /** 鑾峰彇鎸囧畾棰樺簱鐨勭粌涔犻鐩?*/
  getQuestionsByBank(bankId: number, params?: {
    type?: string;
    difficulty?: string;
  }): Promise<GetQuestionListItem[]>;

  /** 鑾峰彇鎸囧畾绔犺妭鐨勭粌涔犻鐩?*/
  getQuestionsByChapter(chapterId: number, params?: {
    type?: string;
    difficulty?: string;
  }): Promise<GetQuestionListItem[]>;

  /** 鑾峰彇鍗曢璇︽儏锛堝埛棰橈紝涓嶅惫绛旀锛?*/
  getQuestionDetail(id: number): Promise<GetQuestionDetail>;

  /** 鏌ョ湅棰樼洰瑙ｆ瀽锛堟彁浜ょ瓟妗堝悗锛?*/
  getQuestionAnalysis(id: number): Promise<QuestionAnalysisItem>;

  /** 创建练习会话 */
  createSession(params: CreatePracticeSessionParam): Promise<GetPracticeSessionDetail>;

  /** 获取最新进行中的会话 */
  getLatestSession(params?: {
    session_type?: SessionType;
    bank_id?: number;
    chapter_id?: number;
  }): Promise<GetPracticeSessionDetail>;

  /** 获取会话列表（分页在外部处理） */
  getSessions(params?: PracticeSessionQueryParam): Promise<PageData<GetPracticeSessionListItem>>;

  /** 获取会话详情 */
  getSession(id: number): Promise<GetPracticeSessionDetail>;

  /** 提交会话 */
  submitSession(id: number, params: SubmitPracticeSessionParam): Promise<SubmitPracticeSessionResult>;

  /** 放弃会话 */
  abandonSession(id: number): Promise<void>;

  /** 删除会话 */
  deleteSession(id: number): Promise<void>;

  /** 批量提交/更新答题记录 */
  upsertRecords(id: number, params: BatchUpsertPracticeRecordsParam): Promise<void>;

  /** 获取答题记录详情 */
  getRecord(id: number): Promise<GetPracticeRecordDetail>;

  /** 获取答题记录列表 */
  getRecords(params?: {
    session_id?: number;
    question_id?: number;
  }): Promise<PageData<GetPracticeRecordListItem>>;

  /** 获取会话的所有答题记录 */
  getSessionRecords(id: number): Promise<GetPracticeRecordDetail[]>;

  /** 获取会话报告 */
  getSessionReport(id: number): Promise<SessionReport>;

  /** 获取会话解析 */
  getSessionSolution(id: number): Promise<unknown>;
}

export function createPracticeModule(client: ApiClient): PracticeModule {
  return {
    getQuestions(params) {
      return client.get<GetQuestionListItem[]>('/practice/questions', {
        params: params as Record<string, unknown>,
      });
    },

    getQuestionsByBank(bankId, params) {
      return client.get<GetQuestionListItem[]>(`/practice/banks/${bankId}/questions`, {
        params: params as Record<string, unknown>,
      });
    },

    getQuestionsByChapter(chapterId, params) {
      return client.get<GetQuestionListItem[]>(`/practice/chapters/${chapterId}/questions`, {
        params: params as Record<string, unknown>,
      });
    },

    getQuestionDetail(id) {
      return client.get<GetQuestionDetail>(`/practice/questions/${id}`);
    },

    getQuestionAnalysis(id) {
      return client.get<QuestionAnalysisItem>(`/practice/questions/${id}/analysis`);
    },

    createSession(params) {
      return client.post<GetPracticeSessionDetail>('/session', params);
    },

    getLatestSession(params) {
      return client.get<GetPracticeSessionDetail>('/session/latest', {
        params: params as Record<string, unknown>,
      });
    },

    getSessions(params) {
      return client.get<PageData<GetPracticeSessionListItem>>('/session', {
        params: params as Record<string, unknown>,
      });
    },

    getSession(id) {
      return client.get<GetPracticeSessionDetail>(`/session/${id}`);
    },

    submitSession(id, params) {
      return client.post<SubmitPracticeSessionResult>(`/session/${id}/submit`, params);
    },

    abandonSession(id) {
      return client.post<void>(`/session/${id}/abandon`);
    },

    deleteSession(id) {
      return client.delete<void>(`/session/${id}`);
    },

    upsertRecords(id, params) {
      return client.post<void>(`/session/${id}/records`, params);
    },

    getRecord(id) {
      return client.get<GetPracticeRecordDetail>(`/session/records/${id}`);
    },

    getRecords(params) {
      return client.get<PageData<GetPracticeRecordListItem>>('/session/records', {
        params: params as Record<string, unknown>,
      });
    },

    getSessionRecords(id) {
      return client.get<GetPracticeRecordDetail[]>(`/session/${id}/records`);
    },

    getSessionReport(id) {
      return client.get<SessionReport>(`/session/${id}/report`);
    },

    getSessionSolution(id) {
      return client.get<unknown>(`/session/${id}/solution`);
    },
  };
}


import type { ApiClient } from '../client/types';
import type {
  BatchImportParam,
  BatchImportResult,
  CreateQuestionParam,
  GetQuestionDetail,
  GetQuestionListItem,
  GetQuestionNoteDetail,
  GetQuestionSolution,
  GetQuestionStatisticsDetail,
  QuestionAnalysisItem,
  QuestionListParams,
  QuestionOptionStatsItem,
  UpdateQuestionParam,
} from '../types';
import type { PageData } from '../types/common';

export type QuestionListResult =
  | PageData<GetQuestionListItem>
  | GetQuestionListItem[];

export interface QuestionModule {
  getDetail(id: number): Promise<GetQuestionDetail>;
  getList(params?: QuestionListParams): Promise<QuestionListResult>;
  getAnalysis(id: number): Promise<QuestionAnalysisItem>;
  getSolution(id: number, userAnswer?: string): Promise<GetQuestionSolution>;
  markAnalysisHelpful(id: number, isHelpful: boolean): Promise<void>;
  getStatistics(id: number): Promise<GetQuestionStatisticsDetail>;
  getOptionStats(
    id: number,
    params?: { bank_id?: number; chapter_id?: number },
  ): Promise<QuestionOptionStatsItem[]>;
  checkFavorites(questionIds: number[]): Promise<Record<number, boolean>>;
  getNotes(questionIds: number[]): Promise<Record<number, GetQuestionNoteDetail | null>>;
  create(data: CreateQuestionParam): Promise<void>;
  update(id: number, data: UpdateQuestionParam): Promise<void>;
  remove(ids: number[]): Promise<void>;
  batchImport(data: BatchImportParam): Promise<BatchImportResult>;
}

export function createQuestionModule(client: ApiClient): QuestionModule {
  return {
    getDetail(id) {
      return client.get<GetQuestionDetail>(`/qbank/questions/${id}`);
    },

    getList(params) {
      return client.get<QuestionListResult>('/qbank/questions', {
        params: params as Record<string, unknown>,
      });
    },

    getAnalysis(id) {
      return client.get<QuestionAnalysisItem>(`/qbank/questions/${id}/analysis`);
    },

    getSolution(id, userAnswer) {
      return client.get<GetQuestionSolution>(`/qbank/questions/${id}/solution`, {
        params: userAnswer ? { user_answer: userAnswer } : undefined,
      });
    },

    markAnalysisHelpful(id, isHelpful) {
      return client.post(`/qbank/questions/${id}/analysis/helpful`, {
        is_helpful: isHelpful,
      });
    },

    getStatistics(id) {
      return client.get<GetQuestionStatisticsDetail>(`/qbank/questions/${id}/statistics`);
    },

    getOptionStats(id, params) {
      return client.get<QuestionOptionStatsItem[]>(`/qbank/questions/${id}/option-stats`, {
        params: params as Record<string, unknown>,
      });
    },

    checkFavorites(questionIds) {
      return client.get<Record<number, boolean>>('/qbank/questions/favorites', {
        params: { question_ids: questionIds.join(',') },
      });
    },

    getNotes(questionIds) {
      return client.get<Record<number, GetQuestionNoteDetail | null>>('/qbank/questions/notes', {
        params: { question_ids: questionIds.join(',') },
      });
    },

    create(data) {
      return client.post('/qbank/questions', data);
    },

    update(id, data) {
      return client.put(`/qbank/questions/${id}`, data);
    },

    remove(ids) {
      return client.delete('/qbank/questions', { ids });
    },

    batchImport(data) {
      return client.post<BatchImportResult>('/qbank/questions/import', data);
    },
  };
}

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
      return client.get<GetQuestionDetail>(`/questions/${id}`);
    },

    getList(params) {
      return client.get<QuestionListResult>('/questions', {
        params: params as Record<string, unknown>,
      });
    },

    getAnalysis(id) {
      return client.get<QuestionAnalysisItem>(`/questions/${id}/analysis`);
    },

    getSolution(id, userAnswer) {
      return client.get<GetQuestionSolution>(`/questions/${id}/solution`, {
        params: userAnswer ? { user_answer: userAnswer } : undefined,
      });
    },

    markAnalysisHelpful(id, isHelpful) {
      return client.post(`/questions/${id}/analysis/helpful`, {
        is_helpful: isHelpful,
      });
    },

    getStatistics(id) {
      return client.get<GetQuestionStatisticsDetail>(`/questions/${id}/statistics`);
    },

    getOptionStats(id, params) {
      return client.get<QuestionOptionStatsItem[]>(`/questions/${id}/option-stats`, {
        params: params as Record<string, unknown>,
      });
    },

    checkFavorites(questionIds) {
      return client.get<Record<number, boolean>>('/questions/favorites', {
        params: { question_ids: questionIds.join(',') },
      });
    },

    getNotes(questionIds) {
      return client.get<Record<number, GetQuestionNoteDetail | null>>('/questions/notes', {
        params: { question_ids: questionIds.join(',') },
      });
    },

    create(data) {
      return client.post('/questions', data);
    },

    update(id, data) {
      return client.put(`/questions/${id}`, data);
    },

    remove(ids) {
      return client.delete('/questions', { ids });
    },

    batchImport(data) {
      return client.post<BatchImportResult>('/questions/import', data);
    },
  };
}


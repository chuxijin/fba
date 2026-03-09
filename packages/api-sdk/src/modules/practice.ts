import type { ApiClient } from '../client/types';
import type {
  GetQuestionDetail,
  GetQuestionListItem,
  QuestionAnalysisItem,
} from '../types';

export interface PracticeModule {
  /** 获取练习题目列表（按筛选条件） */
  getQuestions(params?: {
    bank_id?: number;
    chapter_id?: number;
    type?: string;
    difficulty?: string;
  }): Promise<GetQuestionListItem[]>;

  /** 获取指定题库的练习题目 */
  getQuestionsByBank(bankId: number, params?: {
    type?: string;
    difficulty?: string;
  }): Promise<GetQuestionListItem[]>;

  /** 获取指定章节的练习题目 */
  getQuestionsByChapter(chapterId: number, params?: {
    type?: string;
    difficulty?: string;
  }): Promise<GetQuestionListItem[]>;

  /** 获取单题详情（刷题，不含答案） */
  getQuestionDetail(id: number): Promise<GetQuestionDetail>;

  /** 查看题目解析（提交答案后） */
  getQuestionAnalysis(id: number): Promise<QuestionAnalysisItem>;
}

export function createPracticeModule(client: ApiClient): PracticeModule {
  return {
    getQuestions(params) {
      return client.get<GetQuestionListItem[]>('/qbank/practice/questions', {
        params: params as Record<string, unknown>,
      });
    },

    getQuestionsByBank(bankId, params) {
      return client.get<GetQuestionListItem[]>(`/qbank/practice/banks/${bankId}/questions`, {
        params: params as Record<string, unknown>,
      });
    },

    getQuestionsByChapter(chapterId, params) {
      return client.get<GetQuestionListItem[]>(`/qbank/practice/chapters/${chapterId}/questions`, {
        params: params as Record<string, unknown>,
      });
    },

    getQuestionDetail(id) {
      return client.get<GetQuestionDetail>(`/qbank/practice/questions/${id}`);
    },

    getQuestionAnalysis(id) {
      return client.get<QuestionAnalysisItem>(`/qbank/practice/questions/${id}/analysis`);
    },
  };
}

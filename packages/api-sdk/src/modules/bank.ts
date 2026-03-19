import type { ApiClient } from '../client/types';
import type {
  BankListParams,
  CreateBankParam,
  GetBankDetail,
  GetBankDetailWithChapters,
  GetBankQuestionsAllResult,
  UpdateBankParam,
} from '../types';

export interface BankModule {
  getRecommend(): Promise<GetBankDetail[]>;
  getDetail(id: number): Promise<GetBankDetailWithChapters>;
  getList(params?: BankListParams): Promise<GetBankDetail[]>;
  getAllQuestions(
    bankId: number,
    params?: { offset?: number; limit?: number },
  ): Promise<GetBankQuestionsAllResult>;
  create(data: CreateBankParam): Promise<void>;
  update(id: number, data: UpdateBankParam): Promise<void>;
  remove(ids: number[]): Promise<void>;
}

export function createBankModule(client: ApiClient): BankModule {
  return {
    getRecommend() {
      return client.get<GetBankDetail[]>('/banks/recommend');
    },

    getDetail(id) {
      return client.get<GetBankDetailWithChapters>(`/banks/${id}`);
    },

    getList(params) {
      return client.get<GetBankDetail[]>('/banks', {
        params: params as Record<string, unknown>,
      });
    },

    getAllQuestions(bankId, params) {
      return client.get<GetBankQuestionsAllResult>(`/banks/${bankId}/questions/all`, {
        params: params as Record<string, unknown>,
      });
    },

    create(data) {
      return client.post('/banks', data);
    },

    update(id, data) {
      return client.put(`/banks/${id}`, data);
    },

    remove(ids) {
      return client.delete('/banks', { ids });
    },
  };
}


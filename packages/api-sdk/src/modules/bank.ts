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
      return client.get<GetBankDetail[]>('/qbank/banks/recommend');
    },

    getDetail(id) {
      return client.get<GetBankDetailWithChapters>(`/qbank/banks/${id}`);
    },

    getList(params) {
      return client.get<GetBankDetail[]>('/qbank/banks', {
        params: params as Record<string, unknown>,
      });
    },

    getAllQuestions(bankId, params) {
      return client.get<GetBankQuestionsAllResult>(`/qbank/banks/${bankId}/questions/all`, {
        params: params as Record<string, unknown>,
      });
    },

    create(data) {
      return client.post('/qbank/banks', data);
    },

    update(id, data) {
      return client.put(`/qbank/banks/${id}`, data);
    },

    remove(ids) {
      return client.delete('/qbank/banks', { ids });
    },
  };
}

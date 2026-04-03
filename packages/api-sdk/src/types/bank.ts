import type { GetQuestionWithAnswer } from './question';

export type BankType = 1 | 2 | 3;

export type BankStatus = 0 | 1;

export type BankScope = 0 | 1;

export interface GetChapterTree {
  id: number;
  bank_id: number;
  name: string;
  parent_id: number | null;
  sort_order: number;
  q_count_cache: number;
  is_active: boolean;
  children: GetChapterTree[];
}

export interface BankSchemaBase {
  cat_id: number;
  name: string;
  code: string;
  desc: string | null;
  cover_url: string | null;
  difficulty: number | null;
  bank_type: BankType;
  scene_mask: number;
  parent_id: number | null;
  chapter_source_bank_id?: number | null;
  status: number;
  scope: number;
  access_entitlement_code?: string | null;
}

export interface GetBankDetail extends BankSchemaBase {
  id: number;
  q_count_cache: number;
  total_score_cache: number;
  buy_count: number;
  created_by: number;
  updated_by: number | null;
  created_time: string;
  updated_time: string | null;
}

export interface GetBankDetailWithChapters extends GetBankDetail {
  chapters: GetChapterTree[];
}

export interface GetBankQuestionsAllResult {
  total: number;
  offset: number;
  limit: number;
  items: GetQuestionWithAnswer[];
}

export interface CreateBankParam extends BankSchemaBase {}

export interface UpdateBankParam extends BankSchemaBase {}

export interface BankListParams {
  cat_id?: number;
  status?: BankStatus;
  scope?: BankScope;
  keyword?: string;
  bank_type?: BankType;
  parent_id?: number;
}

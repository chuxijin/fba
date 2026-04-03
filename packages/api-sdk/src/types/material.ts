export interface ChapterBankBrief {
  id: number;
  name: string;
  code: string;
}

export interface MaterialSchemaBase {
  bank_id: number;
  title: string;
  content: string;
  category_id: number | null;
  source: string | null;
  year: number | null;
  sort_order: number;
  is_active: boolean;
}

export interface GetMaterialDetail extends MaterialSchemaBase {
  id: number;
  created_time: string;
  updated_time: string | null;
}

export interface GetMaterialWithRelationDetail extends GetMaterialDetail {
  bank: ChapterBankBrief | null;
  question_count: number;
}

export interface GetMaterialListItem {
  id: number;
  bank_id: number;
  title: string;
  source: string | null;
  year: number | null;
  sort_order: number;
  is_active: boolean;
  created_time: string;
}

export interface MaterialListParams {
  bank_id?: number;
  category_id?: number;
  keyword?: string;
  is_active?: boolean;
  year?: number;
}

export interface CreateMaterialParam extends MaterialSchemaBase {}

export interface UpdateMaterialParam extends MaterialSchemaBase {}

export interface LinkQuestionParam {
  question_ids: number[];
}

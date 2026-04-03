import type { PaginationParams } from './common';

export type GongkaoEntity = Record<string, unknown>;

export interface GongkaoListParams extends PaginationParams {
  [key: string]: unknown;
}

export interface GkShizhenResult {
  id: number;
  daily_date?: string;
  original?: string;
  summary?: string;
  created_time: string;
  updated_time?: string;
  created_by?: number;
  updated_by?: number;
}

export interface GkShizhenParams extends PaginationParams {
  daily_date?: string;
}

export interface GkCiyuResult {
  id: number;
  word: string;
  meaning?: string;
  pinyin?: string;
  synonym?: string;
  antonym?: string;
  example?: string;
  category?: string;
  source?: string;
  emotion?: string;
  confusion?: string;
  frequency?: number;
  view_count: number;
  created_time: string;
  updated_time?: string;
}

export interface GkCiyuParams extends PaginationParams {
  word?: string;
  category?: string;
  emotion?: string;
  frequency?: number;
}

export interface GkGuanmeiResult {
  id: number;
  daily_date: string;
  left_content: string;
  right_content: string;
  view_count: number;
  created_time: string;
  updated_time?: string;
}

export interface GkGuanmeiParams extends PaginationParams {
  daily_date?: string;
}

export interface GkShipingResult {
  id: number;
  title?: string;
  source?: string;
  author?: string;
  keywords?: string;
  content?: string;
  summary?: string;
  daily_date?: string;
  view_count?: number;
  created_time?: string;
  updated_time?: string;
}

export interface GkShipingParams extends PaginationParams {
  title?: string;
  source?: string;
  author?: string;
  keywords?: string;
  daily_date?: string;
}

export interface GkQuestionResult {
  id: number;
  title: string;
  type: string;
  category_id: number;
  material_ids?: number[];
  difficulty?: number;
  year?: number;
  source?: string;
  tags?: string[];
  score?: number;
  view_count: number;
  status: boolean;
  sort_order: number;
  created_time: string;
  updated_time?: string;
}

export interface GkQuestionOptionResult {
  id: number;
  question_id: number;
  option_key: string;
  option_content: string;
  sort_order: number;
}

export interface GkQuestionAnswerResult {
  id: number;
  question_id: number;
  source: string;
  answer_keys?: string;
  answer?: string;
  analysis?: string;
  analysis_video_url?: string;
  knowledge_points?: string[];
  reference_materials?: string;
  is_official: boolean;
}

export interface GkMaterialResult {
  id: number;
  title: string;
  content: string;
  category_id: number;
  year?: number;
  source?: string;
  tags?: string[];
}

export interface GkQuestionParams extends PaginationParams {
  title?: string;
  type?: string;
  category_id?: number;
  material_id?: number;
  year?: number;
  source?: string;
  status?: boolean;
}

export interface GkMaterialParams extends PaginationParams {
  title?: string;
  category_id?: number;
  year?: number;
  source?: string;
  status?: boolean;
}

export interface GkContentResult extends GongkaoEntity {
  id: number;
  title?: string;
  slug?: string;
  view_count?: number;
  created_time?: string;
  updated_time?: string;
}

export interface GkContentParams extends PaginationParams {
  title?: string;
  category_id?: number;
  tag?: string;
  is_pinned?: boolean;
  is_public?: boolean;
  is_published?: boolean;
  content_type?: string;
  daily_date?: string;
}

export interface GkGangweiResult extends GongkaoEntity {
  id: number;
  year?: number;
  exam_type?: string;
  region?: string;
  dept_name?: string;
  position_name?: string;
  position_code?: string;
}

export interface GkGangweiParams extends PaginationParams {
  year?: number;
  exam_type?: string;
  region?: string;
  dept_name?: string;
  position_name?: string;
  position_code?: string;
}

import type { PaginationParams } from './common';

export interface ContentResult {
  id: number;
  app_code: string;
  title: string;
  slug?: string;
  summary?: string;
  cover_image?: string;
  content_json?: any;
  content_html?: string;
  category_id?: number;
  tags?: string[];
  is_pinned: boolean;
  is_public: boolean;
  is_published: boolean;
  publish_time?: string;
  view_count: number;
  sort_order: number;
  extra?: Record<string, any>;
  created_time: string;
  updated_time?: string;
  created_by?: number;
  updated_by?: number;
}

export interface ContentListDetail extends Omit<ContentResult, 'content_json' | 'content_html'> {}

export interface ContentParams extends PaginationParams {
  app_code?: string;
  category_id?: number;
  is_published?: boolean;
}

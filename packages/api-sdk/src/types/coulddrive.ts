import type { PaginationParams } from './common';

export type CoulddriveDriveType = 'BaiduDrive' | 'QuarkDrive' | 'AlistDrive' | 'LocalFile' | string;

export interface CoulddriveResourceListParams extends PaginationParams {
  category_id?: number;
  resource_type?: string;
  url_type?: CoulddriveDriveType;
  status?: number;
  expired_type?: number;
  user_id?: number;
  is_deleted?: boolean;
  keyword?: string;
}

export interface CoulddriveResourceListItem {
  id: number;
  category_id: number;
  category_name?: string | null;
  main_name: string;
  title?: string | null;
  resource_type: string;
  description?: string | null;
  resource_intro?: string | null;
  url_type: CoulddriveDriveType;
  url: string;
  extract_code?: string | null;
  local_file_path?: string | null;
  file_type?: string | null;
  file_size?: number | null;
  view_count: number;
  hot: number;
  status: number;
  audit_status: number;
  expired_type: number;
  expired_at?: string | null;
  created_time: string;
  updated_time?: string | null;
}

export interface CoulddriveResourceKnowledgeItem extends CoulddriveResourceListItem {
  content?: string | null;
}

export interface CoulddriveResourceVectorSearchParams {
  query: string;
  category_id?: number;
  limit?: number;
  similarity_threshold?: number;
  include_content?: boolean;
}

export interface CoulddriveResourceVectorSearchResultItem {
  resource: CoulddriveResourceListItem;
  similarity: number;
}

export interface CoulddriveResourceVectorSearchKnowledgeResultItem {
  resource: CoulddriveResourceKnowledgeItem;
  similarity: number;
}

export interface CoulddriveResourceVectorizeParams {
  resource_id?: number;
  batch_size?: number;
}

export interface CoulddriveResourceVectorizeResult {
  count?: number;
}

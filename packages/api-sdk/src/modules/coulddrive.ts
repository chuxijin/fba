import type { ApiClient } from '../client/types';
import type { PageData } from '../types/common';
import type {
  CoulddriveResourceListItem,
  CoulddriveResourceListParams,
  CoulddriveResourceVectorSearchKnowledgeResultItem,
  CoulddriveResourceVectorizeParams,
  CoulddriveResourceVectorizeResult,
  CoulddriveResourceVectorSearchParams,
  CoulddriveResourceVectorSearchResultItem,
} from '../types/coulddrive';
import { createScopedClient, type ScopedApiClient } from './_shared';

export interface CoulddriveModule {
  request: ScopedApiClient;
  resource: {
    getList(params?: CoulddriveResourceListParams): Promise<PageData<CoulddriveResourceListItem>>;
    getHot(categoryId?: number, limit?: number): Promise<CoulddriveResourceListItem[]>;
    getDetail(resourceId: number): Promise<CoulddriveResourceListItem>;
    vectorize(params?: CoulddriveResourceVectorizeParams): Promise<CoulddriveResourceVectorizeResult>;
    vectorSearch(params: CoulddriveResourceVectorSearchParams): Promise<CoulddriveResourceVectorSearchResultItem[]>;
    vectorSearchKnowledge(
      params: Omit<CoulddriveResourceVectorSearchParams, 'include_content'>,
    ): Promise<CoulddriveResourceVectorSearchKnowledgeResultItem[]>;
  };
}

export function createCoulddriveModule(client: ApiClient): CoulddriveModule {
  const request = createScopedClient(client, '');

  return {
    request,
    resource: {
      getList(params) {
        return request.get<PageData<CoulddriveResourceListItem>>('/resources', {
          params: params as Record<string, unknown>,
        });
      },
      getHot(categoryId, limit = 20) {
        return request.get<CoulddriveResourceListItem[]>('/resources/hot', {
          params: {
            category_id: categoryId,
            limit,
          },
        });
      },
      getDetail(resourceId) {
        return request.get<CoulddriveResourceListItem>(`/resources/${resourceId}`);
      },
      vectorize(params) {
        return request.post<CoulddriveResourceVectorizeResult>('/resources/vectorize', undefined, {
          params: params as Record<string, unknown>,
        });
      },
      vectorSearch(params) {
        return request.get<CoulddriveResourceVectorSearchResultItem[]>('/resources/vector-search', {
          params: {
            ...params,
            include_content: false,
          },
        });
      },
      vectorSearchKnowledge(params) {
        return request.get<CoulddriveResourceVectorSearchKnowledgeResultItem[]>('/resources/vector-search', {
          params: {
            ...params,
            include_content: true,
          },
        });
      },
    },
  };
}

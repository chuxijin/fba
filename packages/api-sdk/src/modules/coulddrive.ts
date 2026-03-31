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
    getHot(categoryId?: number, limit?: number, resourceType?: string | string[]): Promise<CoulddriveResourceListItem[]>;
    recordClick(resourceId: number): Promise<{ click_count: number }>;
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
          headers: { Authorization: '' },
        });
      },
      getHot(categoryId, limit = 20, resourceType) {
        const params: Record<string, unknown> = { limit };
        if (typeof categoryId === 'number') {
          params.category_id = categoryId;
        }
        if (Array.isArray(resourceType)) {
          const resourceTypes = resourceType
            .map(item => String(item || '').trim())
            .filter(Boolean);

          if (resourceTypes.length > 0) {
            params.resource_types = resourceTypes.join(',');
          }
        }
        else if (resourceType) {
          params.resource_type = resourceType;
        }

        return request.get<CoulddriveResourceListItem[]>('/resources/hot', {
          params,
          headers: { Authorization: '' },
        });
      },
      recordClick(resourceId) {
        return request.post<{ click_count: number }>(`/resources/${resourceId}/click`, undefined, {
          headers: { Authorization: '' },
        });
      },
      getDetail(resourceId) {
        return request.get<CoulddriveResourceListItem>(`/resources/${resourceId}`, {
          headers: { Authorization: '' },
        });
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

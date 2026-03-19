import type { ApiClient, RequestConfig } from '../client/types';

export interface ScopedApiClient extends ApiClient {
  prefix: string;
}

function resolveUrl(prefix: string, url: string): string {
  const normalizedPrefix = prefix.replace(/\/+$/, '');
  const normalizedUrl = url.startsWith('/') ? url : `/${url}`;
  return normalizedPrefix ? `${normalizedPrefix}${normalizedUrl}` : normalizedUrl;
}

export function createScopedClient(client: ApiClient, prefix: string): ScopedApiClient {
  return {
    prefix,
    raw<T>(config: RequestConfig): Promise<T> {
      return client.raw<T>({ ...config, url: resolveUrl(prefix, config.url) });
    },
    get<T>(url: string, config?: Partial<RequestConfig>): Promise<T> {
      return client.get<T>(resolveUrl(prefix, url), config);
    },
    post<T>(url: string, data?: unknown, config?: Partial<RequestConfig>): Promise<T> {
      return client.post<T>(resolveUrl(prefix, url), data, config);
    },
    put<T>(url: string, data?: unknown, config?: Partial<RequestConfig>): Promise<T> {
      return client.put<T>(resolveUrl(prefix, url), data, config);
    },
    delete<T>(url: string, data?: unknown, config?: Partial<RequestConfig>): Promise<T> {
      return client.delete<T>(resolveUrl(prefix, url), data, config);
    },
  };
}

import { ApiError, NetworkError, UnauthorizedError } from './errors';
import type { ApiClient, RequestConfig, SdkOptions } from './types';

interface RawResponse<T = unknown> {
  code: number;
  msg: string;
  data: T;
}

interface ParsedAdapterError {
  status?: number;
  raw?: RawResponse;
}

function parseAdapterError(error: unknown): ParsedAdapterError {
  if (!error || typeof error !== 'object') {
    return {};
  }

  const response = (error as { response?: { status?: number; data?: unknown } }).response;
  if (!response) {
    return {};
  }

  const result: ParsedAdapterError = {};
  if (typeof response.status === 'number') {
    result.status = response.status;
  }

  const rawData = response.data;
  if (!rawData || typeof rawData !== 'object') {
    return result;
  }

  const data = rawData as { code?: unknown; msg?: unknown; data?: unknown };
  if (typeof data.code === 'number' && typeof data.msg === 'string') {
    result.raw = {
      code: data.code,
      msg: data.msg,
      data: data.data,
    };
  }

  return result;
}

export function createApiClient(options: SdkOptions): ApiClient {
  const {
    baseURL,
    adapter,
    apiPrefix = '/api/v1',
    getToken,
    timeout = 15_000,
    onUnauthorized,
  } = options;

  async function request<T>(config: RequestConfig): Promise<T> {
    const fullUrl = `${baseURL.replace(/\/+$/, '')}${apiPrefix}${config.url}`;

    const headers: Record<string, string> = { ...config.headers };
    if (getToken) {
      const token = await getToken();
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }
    }

    let raw: RawResponse<T>;
    try {
      raw = await adapter.request<RawResponse<T>>({
        ...config,
        url: fullUrl,
        headers,
        timeout: config.timeout ?? timeout,
      });
    } catch (err) {
      const parsedError = parseAdapterError(err);

      if (parsedError.status === 401 || parsedError.raw?.code === 401) {
        onUnauthorized?.();
        throw new UnauthorizedError(parsedError.raw?.msg);
      }

      if (parsedError.raw) {
        throw new ApiError(parsedError.raw.code, parsedError.raw.msg, parsedError.raw.data);
      }

      throw new NetworkError('网络请求失败，请检查网络连接', err);
    }

    if (raw.code === 401) {
      onUnauthorized?.();
      throw new UnauthorizedError(raw.msg);
    }

    if (raw.code !== 200) {
      throw new ApiError(raw.code, raw.msg, raw.data);
    }

    return raw.data;
  }

  return {
    get<T>(url: string, config?: Partial<RequestConfig>): Promise<T> {
      return request<T>({ method: 'GET', url, ...config });
    },

    post<T>(url: string, data?: unknown, config?: Partial<RequestConfig>): Promise<T> {
      return request<T>({ method: 'POST', url, data, ...config });
    },

    put<T>(url: string, data?: unknown, config?: Partial<RequestConfig>): Promise<T> {
      return request<T>({ method: 'PUT', url, data, ...config });
    },

    delete<T>(url: string, data?: unknown, config?: Partial<RequestConfig>): Promise<T> {
      return request<T>({ method: 'DELETE', url, data, ...config });
    },
  };
}

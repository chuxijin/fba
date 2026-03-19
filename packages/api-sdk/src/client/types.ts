export interface RequestConfig {
  url: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  params?: Record<string, unknown>;
  data?: unknown;
  headers?: Record<string, string>;
  timeout?: number;
}

export interface RequestAdapter {
  request<T = unknown>(config: RequestConfig): Promise<T>;
}

export interface FormDataLike {
  append(name: string, value: unknown, fileName?: string): void;
}

export interface SdkOptions {
  baseURL: string;
  adapter: RequestAdapter;
  apiPrefix?: string;
  getToken?: () => string | undefined | Promise<string | undefined>;
  timeout?: number;
  onUnauthorized?: () => void;
  decryptData?: (base64Str: string) => Promise<unknown>;
}

export interface ApiClient {
  raw<T>(config: RequestConfig): Promise<T>;
  get<T>(url: string, config?: Partial<RequestConfig>): Promise<T>;
  post<T>(url: string, data?: unknown, config?: Partial<RequestConfig>): Promise<T>;
  put<T>(url: string, data?: unknown, config?: Partial<RequestConfig>): Promise<T>;
  delete<T>(url: string, data?: unknown, config?: Partial<RequestConfig>): Promise<T>;
}


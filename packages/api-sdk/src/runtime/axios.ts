import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosStatic } from 'axios';
import type { Config } from '@hey-api/client-axios';

export interface ApiResponseError extends Error {
  code?: number;
  msg?: string;
  status?: number;
  data?: unknown;
}

export interface SetupSdkOptions {
  baseURL: string;
  /** 可选 axios adapter; 小程序端传 axios-miniprogram-adapter, 浏览器端不传 */
  adapter?: AxiosRequestConfig['adapter'];
  /** 鉴权 token 获取函数, 每次请求时调用 */
  getToken?: () => string | undefined | null;
  /** 401 回调, 通常用于跳转登录 */
  onUnauthorized?: () => void;
  /** 业务错误回调 (code !== 200) */
  onError?: (error: ApiResponseError) => void;
  /** 请求超时 (ms), 默认 30000 */
  timeout?: number;
  /** 额外请求头, 每次请求时合并 */
  extraHeaders?: () => Record<string, string>;
}

let sharedInstance: AxiosInstance | null = null;
let pendingBaseURL: string | undefined;

/**
 * hey-api 启动期回调; 返回的 Config 用于 client.gen.ts 中的 createClient 调用。
 * 在 setupSdk 调用前 axios 实例尚未就绪, 这里只 forward override。
 * 真正的 axios 实例由 setupSdk 通过 client.setConfig 后续注入。
 */
export const createClientConfig = <T extends Config>(override?: T): T => {
  const base = {
    baseURL: pendingBaseURL ?? '',
  } as T;
  return { ...base, ...override };
};

function makeError(message: string, partial: Partial<ApiResponseError> = {}): ApiResponseError {
  const err = new Error(message) as ApiResponseError;
  Object.assign(err, partial);
  return err;
}

/**
 * 初始化 SDK; 必须在调用任何生成方法之前执行一次。
 * 内部创建 axios 实例并注入 hey-api 的 generated client。
 */
export async function setupSdk(opts: SetupSdkOptions): Promise<AxiosInstance> {
  pendingBaseURL = opts.baseURL;

  const instance = axios.create({
    baseURL: opts.baseURL,
    adapter: opts.adapter,
    timeout: opts.timeout ?? 30_000,
  });

  instance.interceptors.request.use((config) => {
    const token = opts.getToken?.();
    if (token) {
      config.headers = config.headers ?? {};
      (config.headers as Record<string, string>).Authorization = `Bearer ${token}`;
    }
    const extras = opts.extraHeaders?.();
    if (extras) {
      config.headers = { ...config.headers, ...extras } as typeof config.headers;
    }
    return config;
  });

  instance.interceptors.response.use(
    (res) => {
      const body = res.data;
      if (body && typeof body === 'object' && 'code' in body) {
        const code = (body as { code: number }).code;
        const msg = (body as { msg?: string }).msg;
        const data = (body as { data?: unknown }).data;
        if (code === 401) {
          opts.onUnauthorized?.();
          return Promise.reject(makeError(msg ?? 'unauthorized', { code, msg, status: res.status, data }));
        }
        if (code !== 200 && code !== 0) {
          const err = makeError(msg ?? `business error ${code}`, { code, msg, status: res.status, data });
          opts.onError?.(err);
          return Promise.reject(err);
        }
        return { ...res, data };
      }
      return res;
    },
    (error) => {
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        opts.onUnauthorized?.();
      }
      return Promise.reject(error);
    },
  );

  sharedInstance = instance;

  // 把 axios 实例注入到 generated client
  const mod = await import('../generated/client.gen');
  // AxiosInstance 与 AxiosStatic 同样 callable, 运行时等价
  mod.client.setConfig({ axios: instance as unknown as AxiosStatic, baseURL: opts.baseURL });

  return instance;
}

export function getSdkInstance(): AxiosInstance {
  if (!sharedInstance) {
    throw new Error('SDK not initialized. Call setupSdk() before any API call.');
  }
  return sharedInstance;
}

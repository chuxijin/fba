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
  /**
   * Token 自然过期回调; 仅在响应 msg 为「Token 已过期」时触发。
   * 返回 true 表示已成功刷新, SDK 会自动用新 token 重放原请求;
   * 返回 false 或抛错则走 onUnauthorized 兜底登出。
   */
  onTokenExpired?: () => Promise<boolean>;
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

const TOKEN_EXPIRED_MSG = 'Token 已过期';

type Handle401Result = { replayed: true; value: unknown } | { replayed: false };

/**
 * 统一处理 code/status 为 401 的响应。
 *
 * 三种路径:
 * 1) 外层原始请求 + 「Token 已过期」: 调 onTokenExpired refresh, 成功则重放原请求
 * 2) 内层重放请求再次 401: 直接返回不调 onUnauthorized, 让外层 tryCatch 接住
 * 3) 其它 401 (Token 无效/失效, refresh 自身失败): 调 onUnauthorized 一次
 *
 * 关键: 不依赖 config 字段共享状态, 因为 axios mergeConfig 会浅拷贝产生新对象。
 * 重放路径的「内 vs 外」靠 _retry 标记区分, 但每个分支只在当前调用内读, 不跨调用。
 */
async function handle401(
  instance: AxiosInstance,
  config: AxiosRequestConfig | undefined,
  msg: string | undefined,
  opts: SetupSdkOptions,
): Promise<Handle401Result> {
  if (config) {
    const flagged = config as AxiosRequestConfig & { _retry?: boolean };

    if (flagged._retry) {
      // 内层: 重放还是 401, 把控制权交还外层, 不重复 onUnauthorized
      return { replayed: false };
    }

    if (opts.onTokenExpired && msg === TOKEN_EXPIRED_MSG) {
      flagged._retry = true;
      try {
        const refreshed = await opts.onTokenExpired();
        if (refreshed) {
          try {
            const value = await instance.request(config);
            return { replayed: true, value };
          }
          catch {
            // 重放失败, 落到下方 onUnauthorized
          }
        }
      }
      catch {
        // refresh 自身异常, 落到下方 onUnauthorized
      }
    }
  }

  opts.onUnauthorized?.();
  return { replayed: false };
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
    async (res) => {
      const body = res.data;
      if (body && typeof body === 'object' && 'code' in body) {
        const code = (body as { code: number }).code;
        const msg = (body as { msg?: string }).msg;
        const data = (body as { data?: unknown }).data;
        if (code === 401) {
          const result = await handle401(instance, res.config, msg, opts);
          if (result.replayed) {
            return result.value as typeof res;
          }
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
    async (error) => {
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        const responseBody = error.response.data as { code?: number; msg?: string } | undefined;
        const msg = responseBody?.msg;
        const result = await handle401(instance, error.config, msg, opts);
        if (result.replayed) {
          return result.value;
        }
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

/**
 * SDK 请求适配器接口与配置类型
 *
 * 设计核心：适配器模式（Adapter Pattern）
 * SDK 不绑定任何 HTTP 库，调用方注入自己的请求实现即可
 * - Web 端注入 Axios adapter
 * - 小程序注入 wx.request adapter
 * - App 端注入 uni.request / fetch adapter
 */

/** 请求配置 */
export interface RequestConfig {
  url: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  params?: Record<string, unknown>;
  data?: unknown;
  headers?: Record<string, string>;
  /** 请求超时（毫秒） */
  timeout?: number;
}

/** 请求适配器——调用方必须实现此接口 */
export interface RequestAdapter {
  /**
   * 发送 HTTP 请求并返回**原始响应体**（未拆包的 JSON）
   *
   * SDK 内部会对 `{ code, msg, data }` 做统一拆包和错误判断，
   * 适配器只需负责网络层，将后端返回的 JSON body 原样传回即可。
   */
  request<T = unknown>(config: RequestConfig): Promise<T>;
}

/** SDK 初始化选项 */
export interface SdkOptions {
  /** 后端 API 基础路径，如 `http://127.0.0.1:8000` */
  baseURL: string;

  /** 请求适配器实例 */
  adapter: RequestAdapter;

  /** API 路径前缀，默认 `/api/v1` */
  apiPrefix?: string;

  /**
   * 获取当前认证 Token
   * 返回 `undefined` 表示未登录，SDK 会跳过 Authorization 头
   */
  getToken?: () => string | undefined | Promise<string | undefined>;

  /** 全局请求超时（毫秒），默认 15000 */
  timeout?: number;

  /**
   * 收到 401 时的回调（如跳转登录页）
   * SDK 会先抛出 `UnauthorizedError`，再调用此回调
   */
  onUnauthorized?: () => void;
}

/** SDK 内部使用的标准化客户端接口 */
export interface ApiClient {
  get<T>(url: string, config?: Partial<RequestConfig>): Promise<T>;
  post<T>(url: string, data?: unknown, config?: Partial<RequestConfig>): Promise<T>;
  put<T>(url: string, data?: unknown, config?: Partial<RequestConfig>): Promise<T>;
  delete<T>(url: string, data?: unknown, config?: Partial<RequestConfig>): Promise<T>;
}

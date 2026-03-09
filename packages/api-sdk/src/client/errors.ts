/**
 * SDK 统一错误体系
 *
 * 后端约定：所有接口返回 `{ code: number, msg: string, data?: T }`
 * - code === 200  → 成功
 * - code !== 200  → 业务失败，SDK 抛出 ApiError
 * - HTTP 401      → 认证失败，SDK 抛出 UnauthorizedError
 */

/** 业务级错误——后端返回 code !== 200 时抛出 */
export class ApiError extends Error {
  /** 后端业务错误码 */
  readonly code: number;

  /** 后端原始 msg */
  readonly msg: string;

  /** 后端原始 data（部分错误会携带附加信息） */
  readonly data: unknown;

  constructor(code: number, msg: string, data?: unknown) {
    super(msg);
    this.name = 'ApiError';
    this.code = code;
    this.msg = msg;
    this.data = data;
  }
}

/** 认证失败错误——HTTP 401 或 token 相关错误时抛出 */
export class UnauthorizedError extends ApiError {
  constructor(msg = '认证已过期，请重新登录') {
    super(401, msg);
    this.name = 'UnauthorizedError';
  }
}

/** 网络 / 超时 / 适配器层错误 */
export class NetworkError extends Error {
  /** 原始错误对象 */
  readonly cause: unknown;

  constructor(message: string, cause?: unknown) {
    super(message);
    this.name = 'NetworkError';
    this.cause = cause;
  }
}
